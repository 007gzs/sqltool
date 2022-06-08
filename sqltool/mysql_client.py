# encoding: utf-8
from __future__ import absolute_import, unicode_literals

import logging
import time

from .mysql_pool import MysqlPool

logger = logging.getLogger('mysql_client')


class MySqlClient:
    def __init__(self, **config):
        self.pool = MysqlPool(**config)

    def executemany(self, query, args):
        ret = None
        try:
            start = time.time()
            with self.pool.get_connection().cursor() as cursor:
                ret = cursor.executemany(query, args)
            logger.info("sql query finish %fs: %s %r", time.time() - start, query, args)
        except Exception:
            logger.error("sql query error: %s %r", query, args, exc_info=True)
        return ret

    def query(self, sql, args=None):
        return self._execute(sql=sql, args=args, callback_func=lambda c: c.fetchall(), log_flag='query')

    def get_one(self, sql, args=None):
        return self._execute(sql=sql, args=args, callback_func=lambda c: c.fetchone(), log_flag='get_one')

    def execute(self, sql, args=None):
        return self._execute(sql=sql, args=args, callback_func=lambda c: c.result, log_flag='execute')

    def _execute(self, *, sql, args, callback_func, log_flag):
        ret = None
        try:
            start = time.time()
            with self.pool.get_connection().cursor() as cursor:
                cursor.result = cursor.execute(sql, args)
                ret = callback_func(cursor)
            logger.info("sql %s finish %fs: %s %r", log_flag, time.time() - start, sql, args)
        except Exception:
            logger.error("sql %s error: %s %r", log_flag, sql, args, exc_info=True)
        return ret

    def last_insert_id(self, db_name, table_name):
        sql = """
SELECT
AUTO_INCREMENT as id
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = '%s'
AND TABLE_NAME = '%s'
        """ % (db_name, table_name)
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
