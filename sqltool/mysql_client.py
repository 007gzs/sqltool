# encoding: utf-8
from __future__ import absolute_import, unicode_literals

import enum
import logging
import time

from pymysql.cursors import DictCursor

from .mysql_pool import MysqlPool
from .sql_gen import GenSqlManager

logger = logging.getLogger('mysql_client')


class WhereFlag(enum.Enum):
    NE = "!="
    EQ = "="
    IN = "IN"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    IS = "IS"
    LIKE = "LIKE"


class MySqlClient:
    def __init__(self, **config):
        self.pool = MysqlPool(**config)

    @classmethod
    def gen_insert_sql_args(
        cls,
        items,
        *,
        table_name,
        field_list,
        field_default=None,
        schema_name=None,
        insert_type='INSERT INTO',
        on_duplicate_key_update_fields=()
    ):
        sql_header, sql_tail = GenSqlManager.gen_insert_head_tail(
            table_name,
            field_list,
            schema_name=schema_name,
            insert_type=insert_type,
            on_duplicate_key_update_fields=on_duplicate_key_update_fields
         )
        sql = f"{sql_header} ({','.join(['%s'] * len(field_list))}) {sql_tail}"
        args = []
        if field_default is None:
            field_default = {}
        for item in items:
            args.append([
                GenSqlManager.get_item_value(item, field, field_default, escape=False)
                for field in field_list
            ])
        return sql, args

    @classmethod
    def gen_insert_sql(
        cls,
        items,
        *,
        table_name,
        field_list,
        field_default=None,
        schema_name=None,
        on_duplicate_key_update_fields=()
    ):
        if field_default is None:
            field_default = {}
        return next(GenSqlManager.gen_items_sql(
            items,
            table_name=table_name,
            field_list=field_list,
            field_default=field_default,
            schema_name=schema_name,
            on_duplicate_key_update_fields=on_duplicate_key_update_fields
        ))

    @classmethod
    def gen_where_item(cls, k, v, flag=None):
        if flag is None:
            if v is None:
                flag = WhereFlag.IS
            elif isinstance(v, (tuple, list)):
                flag = WhereFlag.IN
            else:
                flag = WhereFlag.EQ

        flag = WhereFlag(flag)
        if isinstance(v, (tuple, list)):
            v = f'({",".join(map(GenSqlManager.escape_string, v))})'
        else:
            v = GenSqlManager.escape_string(v)
        return f"{k} {flag.value} {v}"

    @classmethod
    def gen_wheres_sql(cls, wheres):
        if isinstance(wheres, dict):
            wheres = list(wheres.items())
        assert isinstance(wheres, (list, tuple))
        where_list = []
        for where in wheres:
            assert len(where) in (2, 3)
            if len(where) == 2:
                k, v = where
                where_list.append(cls.gen_where_item(k, v))
            else:
                k, flag, v = where
                where_list.append(cls.gen_where_item(k, v, flag))
        return " AND ".join(where_list)

    @classmethod
    def gen_select_sql(cls, *, table_name, columns_str='*', schema_name=None, wheres=None, limit=None):
        sql = f"SELECT {columns_str} FROM {GenSqlManager.get_real_table_name(table_name, schema_name)}"
        if wheres:
            sql += " WHERE " + cls.gen_wheres_sql(wheres)
        if limit is not None:
            if isinstance(limit, (list, tuple)):
                assert len(limit) == 2
                start, size = limit
                limit_str = f"{start}, {size}"
            else:
                assert isinstance(limit, int)
                limit_str = str(limit)
            sql += f" LIMIT {limit_str}"
        return sql

    @classmethod
    def gen_delete_sql(cls, *, table_name, schema_name=None, wheres=None):
        sql = f"DELETE FROM {GenSqlManager.get_real_table_name(table_name, schema_name)}"
        assert wheres
        sql += " WHERE " + cls.gen_wheres_sql(wheres)
        return sql

    @classmethod
    def gen_update_sql(cls, *, table_name, update_columns, wheres=None, schema_name=None):
        assert update_columns
        if isinstance(update_columns, dict):
            update_columns = list(update_columns.items())
        assert isinstance(update_columns, (list, tuple))
        sql = f"UPDATE {GenSqlManager.get_real_table_name(table_name, schema_name)} SET"
        sql += ",".join([f"`{key}`={GenSqlManager.escape_string(value)}" for key, value in update_columns])
        if wheres:
            sql += " WHERE " + cls.gen_wheres_sql(wheres)
        return sql

    def insert(
        self,
        items,
        *,
        table_name,
        field_list,
        field_default=None,
        schema_name=None,
        fail_raise=False,
        insert_type='INSERT INTO',
        on_duplicate_key_update_fields=(),
        use_args=True
    ):
        kwargs = {
            "table_name": table_name,
            "field_list": field_list,
            "field_default": field_default,
            "schema_name": schema_name,
            "insert_type": insert_type,
            "on_duplicate_key_update_fields": on_duplicate_key_update_fields
        }
        if use_args:
            sql, args = self.gen_insert_sql_args(items, **kwargs)
            return self.executemany(sql, args, fail_raise=fail_raise)
        else:
            sql = self.gen_insert_sql(items, **kwargs)
            return self.execute(sql, fail_raise=fail_raise)

    def delete(self, *, table_name, schema_name=None, wheres=None, fail_raise=False):
        sql = self.gen_delete_sql(table_name=table_name, schema_name=schema_name, wheres=wheres)
        return self.execute(sql, fail_raise=fail_raise)

    def update(self, *, table_name, update_columns, wheres=None, schema_name=None, fail_raise=False):
        sql = self.gen_update_sql(
            table_name=table_name, update_columns=update_columns, schema_name=schema_name, wheres=wheres
        )
        return self.execute(sql, fail_raise=fail_raise)

    def select(
        self,
        *,
        table_name,
        columns_str='*',
        schema_name=None,
        wheres=None,
        limit=None,
        fail_raise=False,
        cursor_class=None,
        many=True
    ):
        sql = self.gen_select_sql(
            table_name=table_name, columns_str=columns_str, schema_name=schema_name, wheres=wheres, limit=limit
        )
        if many:
            return self.query(sql, fail_raise=fail_raise, cursor_class=cursor_class)
        else:
            return self.get_one(sql, fail_raise=fail_raise, cursor_class=cursor_class)

    def executemany(self, sql, args, fail_raise=False, cursor_class=None):
        return self._execute(
            sql=sql,
            args=args,
            callback_func=lambda c: c.result,
            log_flag='executemany',
            fail_raise=fail_raise,
            cursor_class=cursor_class,
            many=True
        )

    def query(self, sql, args=None, fail_raise=False, cursor_class=None):
        return self._execute(
            sql=sql,
            args=args,
            callback_func=lambda c: c.fetchall(),
            log_flag='query',
            default_ret=[],
            fail_raise=fail_raise,
            cursor_class=cursor_class
        )

    def get_one(self, sql, args=None, fail_raise=False, cursor_class=None):
        return self._execute(
            sql=sql,
            args=args,
            callback_func=lambda c: c.fetchone(),
            log_flag='get_one',
            fail_raise=fail_raise,
            cursor_class=cursor_class
        )

    def execute(self, sql, args=None, fail_raise=False, cursor_class=None):
        return self._execute(
            sql=sql,
            args=args,
            callback_func=lambda c: c.result,
            log_flag='execute',
            fail_raise=fail_raise,
            cursor_class=cursor_class
        )

    def _execute(
        self,
        *,
        sql,
        args,
        callback_func,
        log_flag,
        default_ret=None,
        fail_raise=False,
        cursor_class=None,
        many=False
    ):
        ret = default_ret
        try:
            start = time.time()
            with self.pool.get_connection().cursor(cursor_class) as cursor:
                if many:
                    cursor.result = cursor.executemany(sql, args)
                else:
                    cursor.result = cursor.execute(sql, args)
                ret = callback_func(cursor)
                if not self.pool.autocommit:
                    cursor.execute("commit")
            logger.info("sql %s finish %fs: %s %r", log_flag, time.time() - start, sql, args)
        except Exception as e:
            logger.error("sql %s error: %s %r", log_flag, sql, args, exc_info=True)
            if fail_raise:
                raise e
        return ret

    def get_next_auto_increment(self, db_name, table_name):
        sql = """
SELECT
AUTO_INCREMENT as id
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = '%s'
AND TABLE_NAME = '%s'
        """ % (db_name, table_name)
        ret = self.get_one(sql, cursor_class=DictCursor)
        if ret:
            return ret['id']
        else:
            return None
