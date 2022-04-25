# encoding: utf-8
import logging
import time

import pymysql

if pymysql.version_info >= (1, ):
    from pymysql.converters import escape_string
else:
    from pymysql import escape_string

from .mysql_pool import MysqlPool

logger = logging.getLogger('sql_gen')


class DbBase:
    def __init__(self, **config):
        self.pool = MysqlPool(**config)
        self.db = config['db']

    def executemany(self, sqls):
        ret = None
        try:
            start = time.time()
            with self.pool.get_connection().cursor() as cursor:
                ret = cursor.executemany(sqls)
            logger.info("sql query finish %fs: %s", time.time() - start, sqls)
        except Exception:
            logger.error("sql query error: %s", sqls, exc_info=True)
        return ret

    def query(self, sql):
        ret = None
        try:
            start = time.time()
            with self.pool.get_connection().cursor() as cursor:
                cursor.execute(sql)
                ret = cursor.fetchall()
            logger.info("sql query finish %fs: %s", time.time() - start, sql)
        except Exception:
            logger.error("sql query error: %s", sql, exc_info=True)
        return ret

    def last_insert_id(self, table_name):
        sql = """
SELECT
AUTO_INCREMENT as id
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = '%s'
AND TABLE_NAME = '%s'
        """ % (self.db, table_name)
        ret = None
        try:
            start = time.time()
            with self.pool.get_connection().cursor() as cursor:
                cursor.execute(sql)
                ret = cursor.fetchone()['id']
            logger.info("sql query finish %fs: %s", time.time() - start, sql)
        except Exception:
            logger.error("sql query error: %s", sql, exc_info=True)
        return ret


class GenSqlManager:

    @classmethod
    def gen_insert_head(cls, table_name, field_list):
        return "INSERT INTO `%s` (%s) VALUES \n" % (
            table_name, ",".join(["`%s`" % field for field in field_list])
        )

    @classmethod
    def escape_string(cls, value):
        if value is None:
            return "NULL"
        elif isinstance(value, int):
            return str(value)
        else:
            return "'%s'" % escape_string(str(value))

    @classmethod
    def gen_item_sql(cls, item, field_list, field_default):
        return "(%s)" % ",".join([
            cls.get_item_value(item, field, field_default, escape=True)
            for field in field_list
        ])

    @classmethod
    def get_item_value(cls, item, field, field_default, escape, default_value=None):
        data = item.get(field, field_default.get(field, default_value))
        if escape:
            data = cls.escape_string(data)
        return data

    @classmethod
    def gen_items_sql(cls, items, *, table_name, field_list, field_default, max_sql_size):
        sql_head = cls.gen_insert_head(table_name, field_list)
        sql = ""
        for item in items:
            add_sql = GenSqlManager.gen_item_sql(item, field_list, field_default)
            if len(sql) + len(add_sql) > max_sql_size:
                yield sql
                sql = ""
            if sql:
                sql += ",\n"
            else:
                sql = sql_head
            sql += add_sql
        if sql:
            yield sql


class GenSqlBase(GenSqlManager):
    TABLE_NAME = None
    FIELD_LIST = ()
    FIELD_DEFAULT = {}

    def __init__(self, *args, **kwargs):
        self.items = list()

    def add_item(self, **item):
        self.items.append(item)
        return item

    def gen_sql(self, max_sql_size=1024 * 1024):
        return self.gen_items_sql(
            self.items,
            table_name=self.TABLE_NAME,
            field_list=self.FIELD_LIST,
            field_default=self.FIELD_DEFAULT,
            max_sql_size=max_sql_size
        )


class GenSqlUniqueCheck(GenSqlBase):
    UNIQUE_FIELDS = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique_indexes = {}
        for key in self.get_unique_fields():
            key = self.gen_keys(key)
            assert key not in self.unique_indexes
            for k in key:
                assert k in self.FIELD_LIST
            self.unique_indexes[key] = dict()

    @classmethod
    def gen_keys(cls, keys):
        if not isinstance(keys, (tuple, list)):
            keys = [keys]
        return tuple(keys)

    def on_dup(self, item, dup_items):
        pass

    def find_by_unique(self, key, detail_key):
        key = self.gen_keys(key)
        detail_key = self.gen_keys(detail_key)
        assert key in self.get_unique_fields()
        return self.unique_indexes[key].get(detail_key)

    @classmethod
    def get_unique_fields(cls):
        return cls.UNIQUE_FIELDS

    def add_item(self, **item):
        dup_items = dict()
        dup_keys = dict()
        for key in self.get_unique_fields():
            key = self.gen_keys(key)
            detail_key = self.gen_keys([self.get_item_value(item, k, self.FIELD_DEFAULT, False) for k in key])
            dup_keys[key] = detail_key
            if detail_key in self.unique_indexes[key]:
                dup_items[key] = self.unique_indexes[key][detail_key]
        if dup_items:
            return self.on_dup(item, dup_items)
        ret = super().add_item(**item)
        for key, detail_key in dup_keys.items():
            self.unique_indexes[key][detail_key] = ret
        return ret


class GenSqlAutoId(GenSqlUniqueCheck):
    PK_FILED = 'id'
    UNIQUE_FIELDS = ('id', )
    GEN_ID_KEY = '__GEN_ID__'

    def __init__(self, next_id=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.next_id = next_id
        assert self.PK_FILED in self.FIELD_LIST

    def get_unique_fields(self):
        if self.PK_FILED not in self.UNIQUE_FIELDS:
            return self.UNIQUE_FIELDS + (self.PK_FILED, )
        return self.UNIQUE_FIELDS

    def get_by_pk(self, pk):
        return self.find_by_unique(self.PK_FILED, pk)

    def on_dup(self, item, dup_items):
        if item.get(self.GEN_ID_KEY):
            self.next_id -= 1

    def add_item(self, **item):
        if self.PK_FILED not in item:
            item[self.PK_FILED] = self.next_id
            self.next_id += 1
            item[self.GEN_ID_KEY] = True
        ret = super().add_item(**item)
        ret.pop(self.GEN_ID_KEY, None)
        return ret
