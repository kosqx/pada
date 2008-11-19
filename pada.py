#!/usr/bin/env python
#-*- coding: utf-8 -*-

#DSN = "dbname='test_peda' user='kosqx' host='localhost' password='kos144'"
#DSN = {'host': 'localhost', 'user': 'kosqx', 'passwd': 'kos144', 'db': 'test_mvcc'}
#DSN = {'user': 'kosqx', 'db': 'test_mvcc'}


## Global TODO:
#  - czytanie parametrow polacznia z pliku
#  - przepisywanie parametrow


import re
import time

import unittest


class RowObject(object):
    def __init__(self, data, names):
        self._data = data
        self._names = names

    def __getitem__(self, key):
        if isinstance(key, basestring):
            return self._data[self._names[key]]
        else:
            return self._data[key]

    def __getattr__(self, name):
        if name in self._names:
            return self._data[self._names[name]]
        else:
            raise AttributeError, name

    def __str__(self):
        return str(self._data)

    __repr__ = __str__

    def __list__(self):
        return list(self._data)

    def __iter__(self):
        return iter(self._data)
        
class DataRewriter(object):
    _paramstyle = {
        'qmark':    {'re': r'(\?)',                  'start': 0, 'end': None, 'pattern': '?',             'type':'pos'},
        'format':   {'re': r'(\%s)',                 'start': 0, 'end': None, 'pattern': '%%s',           'type':'pos'},
        'numeric':  {'re': r'(\:[0-9]+)',            'start': 1, 'end': None, 'pattern': ':%(pos)s',      'type':'num'},
        'named':    {'re': r'(\:[a-zA-Z0-9]+)',      'start': 1, 'end': None, 'pattern': ':%(name)s',     'type':'name'},
        'pyformat': {'re': r'(\%\([a-zA-Z0-9]+\)s)', 'start': 2, 'end': -2,   'pattern': '%%(%(name)s)s', 'type':'name'},
    }
    
    def __init__(self, db, user, sql):
        self._db = db
        self._user = user
        self._rewrite(sql)
    
    def _rewrite(self, sql):
        db, user = self._db, self._user
        if (user is None) or (self._type(db) == self._type(user)):
            self._format = None
        else:
            if self._db in ('qmark', 'format', 'numeric'):
                self._format = []
            else:
                self._format = {}
        
        if (user is None) or (db == user):
            self.sql = sql
        else:
            result = []
            for i, p in enumerate(self._parse_sql(sql)):
                if i % 2 == 0:
                    result.append(p)
                else:
                    result.append(self._param(i / 2 + 1, p))
        
            self.sql = ''.join(result)

    def _parse_sql(self, sql):
        regexp = re.compile(self._paramstyle[self._user]['re'])
        return regexp.split(sql)
        
    def _type(self, style):
        return self._paramstyle[style]['type']
        
    def _param(self, pos, name):
        NAME_FORMAT = 'p%d'
        
        name = name[self._paramstyle[self._user]['start']:self._paramstyle[self._user]['end']]
        
        if self._format is not None: 
            types = (self._type(self._db), self._type(self._user))
            
            if types == ('pos', 'num'):
                self._format.append(int(name) - 1)
            if types == ('pos', 'name'):
                self._format.append(name)
                
            if types == ('num', 'pos'):
                self._format.append(pos - 1)
            if types == ('num', 'name'):
                self._format.append(NAME_FORMAT % pos)
                
            if types == ('name', 'pos'):
                self._format[NAME_FORMAT % pos] = pos - 1
                name = NAME_FORMAT % pos
            if types == ('name', 'num'):
                self._format[NAME_FORMAT % int(name)] = int(name) - 1
                name = NAME_FORMAT % int(name)
        
        return self._paramstyle[self._db]['pattern'] % {'pos':pos, 'name':name}
        
    def rewrite_data(self, data):
        """
            print xxx_rewrite({'a':0, 'b':1 ,'c':0}, [3, 7])
            print xxx_rewrite(['a', 'b', 'b'], {'a':0, 'b':1 ,'c':0})
        """
        format = self._format
        if format is None:
            return data
        else:
            result = None
            if format is None:
                result = data
            if isinstance(format, dict):
                result = {}
                for p in format:
                    result[p] = data[format[p]] 
            if isinstance(format, list):
                result = []
                for p in format:
                    result.append(data[p])
            return result

    def rewrite_data_seq(self, data_seq):
        if self._format is None:
            return data_seq
        else:
            return [self.rewrite_data(i) for i in data_seq]

    @staticmethod
    def support_paramstyle(paramstyle):
        return (paramstyle in DataRewriter._paramstyle) or paramstyle is None

def test_speed():
    from time import time
    t = time()
    dr = DataRewriter("numeric", "named", "a = :p1 b = :p2 c = :p3")
    
    for i in xrange(100000):
        dr.rewrite_data({'p1': 1234, 'p2':3.141592, 'p3': 'foo_bar'})
    print time() - t

class DataRewriterTest(unittest.TestCase):
    def testParse(self):
        pass
        #assert DataRewriter('qmark', 'qmark', "WHERE a = ? AND b < ?") == "WHERE a = ? AND b < ?"

    def testRewriteSimple(self):
        tests = [
            ('qmark',    'a = ? b = ? c = ?',                [7, 11, 'foo']),
            ('format',   'a = %s b = %s c = %s',             [7, 11, 'foo']),
            ('numeric',  'a = :1 b = :2 c = :3',             [7, 11, 'foo']),
            ('named',    'a = :p1 b = :p2 c = :p3',          {'p1':7, 'p2':11, 'p3':'foo'}),
            ('pyformat', 'a = %(p1)s b = %(p2)s c = %(p3)s', {'p1':7, 'p2':11, 'p3':'foo'})
        ]
        
        for index, test in enumerate(tests):
            print '----------------\n%s\n-----------------' % test[0]
            for name, sql, data in tests:
                dr = DataRewriter(test[0], name, sql)
                print name
                print dr.sql
                print dr.rewrite_data(data)
                print
                assert dr.sql == test[1]
                assert dr.rewrite_data(data) == test[2]
    
    #def testFromNumeric(self):
        
        #tests = {
            #'qmark':    ['a = ? b = ? c = ?', [123, 144, 123]],
            #'format':   ['a = %s b = %s c = %s', [123, 144, 123]],
            #'numeric':  ['a = :1 b = :2 c = :1', [123, 144]],
            #'named':    ['a = :p1 b = :p2 c = :p1', {'p1':123, 'p2':144}],
            #'pyformat': ['a = %(p1)s b = %(p2)s c = %(p1)s', {'p1':123, 'p2':144}]
        #}
        #for i in tests:
            #print i
            #print '%60s   %r' % DataRewriter.test(i, 'numeric', tests['numeric'][0], tests['numeric'][1])
        

class Database(object):
    class DatabaseIterator:
        def __init__(self, db):
            self._db = db
            self._names = self._db._build_names()

        def __iter__(self):
            return self

        def next(self):
            row = self._db._cur.fetchone()
            if row is None:
                raise StopIteration
            else:
                return RowObject(row, self._names)


    def __iter__(self):
        return Database.DatabaseIterator(self)

    def __init__(self, **config):
        self._time = {}

        if 'paramstyle' in config:
            self.set_paramstyle(config['paramstyle'])
        else:
            self.set_paramstyle(None)


    def set_paramstyle(self, paramstyle):
        #  jeden z 'qmark', 'numeric', 'named', 'format', 'pyformat'
        #if (paramstyle in self._paramstyle_re) or (paramstyle is None):
        if DataRewriter.support_paramstyle(paramstyle):
            self._paramstyle = paramstyle
        else:
            raise 'Unknown paramstyle %r (should be one of %r)' % (paramstyle, self._paramstyle_re.keys())
    
    def get_paramstyle(self):
        return self._paramstyle
    
    def _get_sql(self, sql):
        if isinstance(sql, basestring):
            return sql
        else:
            for i in self._short_names:
                if i in sql:
                    return sql[i]
            # TODO: czy by możne nie zrobić zwracania None zamiast IndexError ?
            return sql['*']

    def _build_names(self):
        result = {}
        for i, d in enumerate(self._cur.description):
            result[d[0].lower()] = i
        return result

    def schema_list(what=''):
      raise 'NotImplemented'
    
    @staticmethod
    def _dict_copy(data, names):
        """
        _dict_copy({'a':'Ala', 'b':'Bala'}, {'a': '1', 'b': '2'}) --> {'1':'Ala', '2':'Bela'}
        """
        result = {}
        for name in names:
            if name in data and data[name] is not None:
                result[names[name]] = data[name]
        return result

    #def connect(dialect=None, driver=None, host=None, dbname=None, user=None, password=None):
    @staticmethod
    def connect(dialect, **config):
        dialects = {
            'postgresql': PostgreSQL,
            'mysql':      MySQL,
            'sqlite':     SQLite,
            'oracle':     Oracle,
            'db2':        DB2,
            'sqlserver':  SQLServer,
        }

        if dialect in dialects:
            db = dialects[dialect](**config)
            return db
        else:
            raise "Dialect %r not supported" % dialect

    def time_start(self, name=None):
        self._time[name] = time.time()

    def time_get(self, name=None):
        try:
            return time.time() - self._time[name]
        except:
            raise 'Unknown clock %r' % name

    def ddl(self, sql):
        asql = self._get_sql(sql)
        if asql is None:
            return self
        self._cur.execute(asql)
        self._db.commit()
        return self

    def _get_rewriter(self, sql):
        return DataRewriter(self._module.paramstyle, self._paramstyle, sql)

    def execute(self, sql, data=None):
        asql = self._get_sql(sql)
        if asql is None:
            return self
        
        dr = self._get_rewriter(asql)
        
        if data is not None:
            self._cur.execute(dr.sql, dr.rewrite_data(data))
        else:
            self._cur.execute(dr.sql)
        
        return self

    def executemany(self, sql, data):
        dr = self._get_rewriter(self._get_sql(sql))
        self._cur.executemany(dr.sql, dr.rewrite_data_seq(data))

    def begin(self, isolation=''):
        isolations = {
            '': None,
            
            0: 'uncommited',
            1: 'commited',
            2: 'repeatable',
            3: 'serializable',
            
            'uncommited':   'uncommited',
            'commited':     'commited',
            'repeatable':   'repeatable',
            'serializable': 'serializable',
        }
        
        isolation = isolation.lower()
        if isolation not in isolations:
            raise "Unknown isolation level %r" % isolation
        else:
            self._do_begin(isolations[isolation])

    def _do_begin(self, isolation):
        # TODO: uspujnic ten slownik
        isolations = {
            'uncommited':   'SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED',
            'commited':     'SET TRANSACTION ISOLATION LEVEL READ COMMITTED',
            'repeatable':   'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ',
            'serializable': 'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE',
        }
        self._cur.execute("BEGIN")
        self._cur.execute(isolations[isolation])
        #print isolations[isolation]

    #TODO:
    # set_autocomit(True|False)
    # savepoint('name')
    # revert ()
    # revert('name') // from savepoint

    def commit(self):
        self._db.commit()

    def list(self):
        result = []
        try:
            #print 'self._cur.rowcount', self._cur.rowcount
            if self._cur.rowcount >= 0: 
                d = self._build_names()
                for i in self._cur.fetchall():
                    result.append(RowObject(i, d))
        except psycopg2.ProgrammingError, e:
            print 'ProgrammingError', e
        return result



class SQLite(Database):
    _short_names = ['li', 'sqlite']
    _short_name  = 'sqlite'
    _full_name  = 'SQLite'
    
    def __init__(self, **config):
        Database.__init__(self, **config)
        import sqlite3
        self._module = sqlite3
        self._db = self._module.connect(config['dbname'])

        self._cur = self._db.cursor()
        
    def schema_list(self, what='table'):
        what = what.lower()

        if what in ('table', 'tables'):
            self._cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        elif what in ('index', 'indexes'):
            self._cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        else:
            raise 'Unsupported'
        data = self._cur.fetchall()
        return [i[0].lower() for i in data]


class Oracle(Database):
    _short_names = ['ora', 'oracle']
    _short_name  = 'oracle'
    _full_name  = 'Oracle'
    
    def __init__(self, **config):
        Database.__init__(self,  **config)
        import cx_Oracle
        self._module = cx_Oracle
        ## TODO: lepsze budowanie napisu
        ## cx_Oracle.connect('kosqx/kos144@localhost:1521/xe')
        dsn = '%(user)s/%(password)s@%(dbname)s' % config
        self._db = self._module.connect(dsn)
        self._cur = self._db.cursor()
        
    def _do_begin(self, isolation):
        # TODO: uspujnic ten slownik
        isolations = {
            'uncommited':   'SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED',
            'commited':     'SET TRANSACTION ISOLATION LEVEL READ COMMITTED',
            'repeatable':   'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ',
            'serializable': 'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE',
        }
        self._cur.execute(isolations[isolation])
        
    def schema_list(self, what='table'):
        what = what.lower()

        if what in ('table', 'tables'):
            self._cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        else:
            raise 'Unsupported'
        data = self._cur.fetchall()
        return [i[0].lower() for i in data]


class DB2(Database):
    _short_names = ['db2']
    _short_name  = 'db2'
    _full_name  = 'DB2'


class SQLServer(Database):
    _short_names = ['server', 'sqlserver']
    _short_name  = 'sqlserver'
    _full_name  = 'SQLServer'


class MySQL(Database):
    _short_names = ['my', 'mysql']
    _short_name  = 'mysql'
    _full_name  = 'MySQL'
    
    def __init__(self,  **config):
        Database.__init__(self, **config)

        if 'driver' not in config or config['driver'] in ['mysqldb', None]:
            import MySQLdb
            self._module = MySQLdb
            args = Database._dict_copy(config, {'host': 'host', 'dbname': 'db', 'user': 'user', 'password': 'passwd'})
            self._db = self._module.connect(**args)
        else:
            raise "Unknow driver %r" % driver

        self._cur = self._db.cursor()

    def schema_list(self, what='table'):
        what = what.lower()

        if what in ('table', 'tables'):
            self._cur.execute("SHOW tables")
            data = self._cur.fetchall()
        else:
            raise 'Unsupported'
        return [i[0].lower() for i in data]


class PostgreSQL(Database):
    _short_names = ['pg', 'psql', 'postgres', 'postgresql']
    _short_name  = 'postgresql'
    _full_name  = 'PostgreSQL'

    def __init__(self, **config):
        Database.__init__(self, **config)

        if 'driver' not in config or config['driver'] in ['psycopg2', None]:
            import psycopg2
            self._module = psycopg2

            args = Database._dict_copy(config, {'host': 'host', 'dbname': 'dbname', 'user': 'user', 'password': 'password'})
            dsn = ' '.join("%s='%s'" % (i, args[i]) for i in args)
            self._db = self._module.connect(dsn)
        else:
            raise "Unknow driver %r" % driver

        self._cur = self._db.cursor()

    def schema_list(self, what='table'):
        what = what.lower()

        if what in ('table', 'tables'):
            self._cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            data = self._cur.fetchall()
        else:
            raise 'Unsupported'
        return [i[0].lower() for i in data]


def rewrite_query(query, mode):
    last = None
    state = ''
    quoted = False
    tmp = []
    result = []
    for c in query:
        if quoted:
            if c == state and last != '\\':
                quoted = False
                tmp.append(c)
                result.append(''.join(tmp))
                tmp = []
            else:
                tmp.append(c)
        else:
            if c in ('"', '\'', '`'):
                state = c
                quoted = True
                result.append(''.join(tmp))
                tmp = [c]
            else:
                tmp.append(c)
        last = c
        
    print result


def main():
    #db = Database.connect(dialect='postgresql', dbname='test_pada', user='kosqx', host='localhost', password='kos144')
    db = Database.connect(dialect='sqlite', dbname='abc.db')
    #db = Database.connect(dialect='oracle', dbname='xe', user='kosqx', password='kos144')
    #db = Database.connect(dialect='mysql', dbname='test_mvcc', user='kosqx', password='kos144')
    
    db.set_paramstyle('numeric')
    
    #print db._get_param('SELECT * FROM tbl WHERE a = :asdf AND b < :ala LIMIT :limit')
    
    #exit()
    
    print db.schema_list('table')

    if 'item' not in db.schema_list('table'):
        print "creating table"
        
        db.execute({
            'pg':  "CREATE TABLE item(id serial PRIMARY KEY, value int)",
            'li':  "CREATE TABLE item(id integer PRIMARY KEY, value int)",
            'ora': "CREATE TABLE item(id integer, value int)",
            'my':  "CREATE TABLE item(id serial PRIMARY KEY, value int) ENGINE=InnoDB",
        })
        db.commit()
        for i in xrange(20):
            db.execute("INSERT INTO item (value) VALUES (:1)", [i])
            
        db.commit()

    '''l = db.execute({'*': "SELECT * FROM item"}).list()
    print l
    for i in l:
        print i[0], i[1], i['id'], i['value'], i.id, i.value, list(i)
    '''
    for i in db.execute({'*': "SELECT * FROM item"}):
        print i.id, i.value



if __name__ == '__main__':
    #rewrite_query(' ala ma "kota" a nie `psa` a tym bardziej "ch\\"omika" lub "x""y"', "")
    #dr = DataRewriter('qmark', 'numeric', 'ala = :1 and b = :2')
    #print dr.sql
    #print dr.rewrite_data(['ala', 'kot'])
    main()
    #test_speed()
    #unittest.main()
    
## driver, adapter, module

'''
Todo:
    sprawdzić czy PK hash jest lepszy od b-tree
    sprawdzic jaka jest różnica przy pogrupowaniu
'''