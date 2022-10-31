from sqltool.mysql_client import MySqlClient
from sqltool.sql_gen import GenSqlAutoId


def test_gen_sql():

    class GenSqlTestParent(GenSqlAutoId):
        TABLE_NAME = 'test_parent'
        FIELD_LIST = ('id', 'name')

    class GenSqlTestChild(GenSqlAutoId):
        TABLE_NAME = 'test_child'
        FIELD_LIST = ('id', 'pid', 'name')
        UNIQUE_FIELDS = (('id', 'name'), )

    parent = GenSqlTestParent()
    child = GenSqlTestChild(next_id=5)
    p = parent.add_item(name="p1")
    child.add_item(pid=p['id'], name='c1')
    child.add_item(pid=p['id'], name='c2')
    p = parent.add_item(name="p2")
    child.add_item(pid=p['id'], name='c4')
    child.add_item(pid=p['id'], name='c5')
    assert list(parent.gen_sql()) == ["INSERT INTO `test_parent` (`id`,`name`) VALUES \n(1,'p1'),\n(2,'p2')"]
    assert list(child.gen_sql()) == [
        "INSERT INTO `test_child` (`id`,`pid`,`name`) VALUES \n(5,1,'c1'),\n(6,1,'c2'),\n(7,2,'c4'),\n(8,2,'c5')"
    ]


def test_on_duplicate_key_update_fields():
    items = (
        {
            'id': 1,
            'col1': 1,
            'col2': 'test1'
        },
        {
            'id': 2,
            'col1': 2,
            'col2': 'test2'
        }
    )
    sql, args = MySqlClient.gen_insert_sql_args(
        items,
        table_name='test',
        field_list=('id', 'col1', 'col2'),
        on_duplicate_key_update_fields=('col2', ('col1', ('col1', '+1')))
    )
    assert args == [[1, 1, 'test1'], [2, 2, 'test2']]
    assert sql == (
        "INSERT INTO `test` (`id`,`col1`,`col2`) VALUES \n"
        " (%s,%s,%s) \n"
        "AS __new_data__ ON DUPLICATE KEY UPDATE `col2`=__new_data__.`col2`,`col1`=__new_data__.`col1` +1"
    )

    sql = MySqlClient.gen_insert_sql(

        items,
        table_name='test',
        field_list=('id', 'col1', 'col2'),
        on_duplicate_key_update_fields=('col2', ('col1', ('col1', '+1')))
    )
    assert sql == (
        "INSERT INTO `test` (`id`,`col1`,`col2`) VALUES \n"
        "(1,1,'test1'),\n"
        "(2,2,'test2') \n"
        "AS __new_data__ ON DUPLICATE KEY UPDATE `col2`=__new_data__.`col2`,`col1`=__new_data__.`col1` +1"
    )
