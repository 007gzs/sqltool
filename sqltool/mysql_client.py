# encoding: utf-8
from __future__ import absolute_import, unicode_literals

import logging
import time

from pymysql.cursors import DictCursor

from .mysql_pool import MysqlPool

logger = logging.getLogger('mysql_client')


class MySqlClient:
    def __init__(self, **config):
        self.pool = MysqlPool(**config)

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
