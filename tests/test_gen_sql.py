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
