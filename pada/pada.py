#!/usr/bin/env python
#-*- coding: utf-8 -*-

import re
import time

import unittest


_paramstyle = {
    'qmark':    {'re': r'(\?)',                  'start': 0, 'end': None, 'pattern': '?',             'type':'pos'},
    'format':   {'re': r'(\%s)',                 'start': 0, 'end': None, 'pattern': '%%s',           'type':'pos'},
    'numeric':  {'re': r'(\:[0-9]+)',            'start': 1, 'end': None, 'pattern': ':%(pos)s',      'type':'num'},
    'named':    {'re': r'(\:[a-zA-Z0-9]+)',      'start': 1, 'end': None, 'pattern': ':%(name)s',     'type':'name'},
    'pyformat': {'re': r'(\%\([a-zA-Z0-9]+\)s)', 'start': 2, 'end': -2,   'pattern': '%%(%(name)s)s', 'type':'name'},
}

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

    def _str(self):
        reverted_names = dict([(self._names[key], key) for key in self._names])
        return ', '.join('%s=%r' % (reverted_names[i], v) for i, v in enumerate(self._data))
    
    def __str__(self):
        return '(' + self._str() + ')'

    def __repr__(self):
        return 'RowObject(' + self._str() + ')'

    def __len__(self):
        return len(self._data)

    def __list__(self):
        return list(self._data)

    def __iter__(self):
        return iter(self._data)


class Cache(object):
    def __init__(self, size):
        self._size = size
        self._old = {}
        self._new = {}
    
    def __len__(self):
        return len(self._new) + len(self._old)
    
    def __contains__(self, key):
        return (key in self._new) or (key in self._old)
        
    def __getitem__(self, key):
        if key in self._new:
            return self._new[key]
        else:
            return self._old[key]
    
    def __setitem__(self, key, value):
        if key in self._new:
            self._new[key] = value
        elif key in self._old:
            if len(self._new) >= self._size:
                self._old = self._new
                self._new = {}
            else:
                del self._old[key]
            self._new[key] = value
        else:
            if len(self._new) >= self._size:
                self._old = self._new
                self._new = {}
            self._new[key] = value
    
    def __delitem__(self, key):
        if key in self._new:
            del self._new[key]
        else:
            del self._old[key]
            
    def clear(self):
        self._old = {}
        self._new = {}

    def __repr__(self):
        return 'new:%r old:%r' % (self._new, self._old)


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = Cache(3)
        for i in xrange(9):
            self.cache[str(i)] = i
    
    def testLen(self):
        assert len(self.cache) >= 3
    
    def testIn(self):
        assert '6' in self.cache
        assert '7' in self.cache
        assert '8' in self.cache

    def testGet(self):
        assert self.cache['6'] == 6
        assert self.cache['7'] == 7
        assert self.cache['8'] == 8
        
    def testSet(self):
        self.cache['6'] = 66
        self.cache['x'] = 'foo'
        
        assert self.cache['8'] == 8
        assert self.cache['6'] == 66
        assert self.cache['x'] == 'foo'
        
    def testDel(self):
        del self.cache['7']
        assert '7' not in self.cache
        
    def testClear(self):
        self.cache.clear()
        assert '8' not in self.cache
        assert len(self.cache) == 0
        
    
class DataRewriter(object):
    #_paramstyle = {
        #'qmark':    {'re': r'(\?)',                  'start': 0, 'end': None, 'pattern': '?',             'type':'pos'},
        #'format':   {'re': r'(\%s)',                 'start': 0, 'end': None, 'pattern': '%%s',           'type':'pos'},
        #'numeric':  {'re': r'(\:[0-9]+)',            'start': 1, 'end': None, 'pattern': ':%(pos)s',      'type':'num'},
        #'named':    {'re': r'(\:[a-zA-Z0-9]+)',      'start': 1, 'end': None, 'pattern': ':%(name)s',     'type':'name'},
        #'pyformat': {'re': r'(\%\([a-zA-Z0-9]+\)s)', 'start': 2, 'end': -2,   'pattern': '%%(%(name)s)s', 'type':'name'},
    #}
    
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
        regexp = re.compile(_paramstyle[self._user]['re'])
        return regexp.split(sql)
        
    def _type(self, style):
        return _paramstyle[style]['type']
        
    def _param(self, pos, name):
        NAME_FORMAT = 'p%d'
        
        name = name[_paramstyle[self._user]['start']:_paramstyle[self._user]['end']]
        
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
        
        return _paramstyle[self._db]['pattern'] % {'pos':pos, 'name':name}
        
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
        return (paramstyle in _paramstyle) or (paramstyle is None)

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

    def is_dialect(self, name):
        return name in self._short_names

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
        if self._cur.description is not None:
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

    # TODO: timer with pause/resume feature, 
    # use {'name', [previous_counted_time, time_of_last_start]}

    def time_start(self, name=None):
        self._time[name] = [0.0, time.time()]

    def time_get(self, name=None):
        if name in self._time:
            if self._time[name][1] is None:
                return self._time[name][0]
            else:
                return (time.time() - self._time[name][1]) + self._time[name][0]
        else:
            raise 'Unknown clock %r' % name
        
    def time_pause(self, name=None):
        if name in self._time:
            self._time[name] = [self.get_time(name), None]
        else:
            raise 'Unknown clock %r' % name
    
    def time_resume(self, name=None):
        assert self._time[name][1] is None, "Time was not been paused"
        if name in self._time:
            self._time[name] = [self._time[name][0], time.time()]
        else:
            raise 'Unknown clock %r' % name

    def ddl(self, sql):
        asql = self._get_sql(sql)
        if asql is None:
            return self
        if isinstance(asql, (list, tuple)):
            for i in asql:
                print i
                self._cur.execute(i)
        else:
            self._cur.execute(asql)
        self._db.commit()
        return self

    def _get_rewriter(self, sql):
        return DataRewriter(self._module.paramstyle, self._paramstyle, sql)

    def _just_execute(self, sql, data=None):
        self._cur.execute(sql, data)
        return self

    def execute(self, sql, data=None):
        asql = self._get_sql(sql)
        if asql is None:
            return self

        if data is not None:
            dr = self._get_rewriter(asql)
            print 'execute.rewrite', repr(dr.sql), dr.rewrite_data(data)
            self._cur.execute(dr.sql, dr.rewrite_data(data))
        else:
            if isinstance(asql, (list, tuple)):
                for i in asql:
                    self._cur.execute(i)
            else:
                self._cur.execute(asql)
        
        return self

    def executemany(self, sql, data):
        dr = self._get_rewriter(self._get_sql(sql))
        self._cur.executemany(dr.sql, dr.rewrite_data_seq(data))
   
    def run(self, sql, data=None):
        "TODO: this is depricated?"
        return self.execute(sql, data).list()

    def insert_id(self, sql, data):
        raise NotImplemented

    def _insert_build(self, table, values, raw={}):
        paramstyle = _paramstyle[self._module.paramstyle]
        pattern = paramstyle['pattern']

        data   = []
        names  = []
        params = []
        
        for key in raw:
            names.append(key)
            params.append(raw[key]) 
        
        for i, key in enumerate(values):
            data.append(values[key])
            names.append(key)
            params.append(pattern % {'pos': i + 1, 'name': key}) 
            
        sql = 'INSERT INTO %s(%s) VALUES(%s)' % (table, ', '.join(names), ', '.join(params))
        
        print sql, data, values
        
        if paramstyle['type'] in ('pos', 'num'):
            return sql, data
        else:
            return sql, values

    def insert(self, table, **values):
        return self._do_insert(table, values)
        #raise NotImplemented

    def begin(self, isolation=''):
        isolations = {
            '':   None,
            None: None,
            
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
        isolations = {
            'uncommited':   'SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED',
            'commited':     'SET TRANSACTION ISOLATION LEVEL READ COMMITTED',
            'repeatable':   'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ',
            'serializable': 'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE',
        }
        self._cur.execute("BEGIN")
        if isolation in isolations:
            self._cur.execute(isolations[isolation])
        #print isolations[isolation]

    #TODO:
    # set_autocomit(True|False)
    # savepoint('name')
    # revert ()
    # revert('name') // from savepoint

    def commit(self):
        self._db.commit()

    def _rowcount(self):
        return self._cur.rowcount

    def list(self):
        result = []
        try:
            #print 'self._cur.rowcount', self._cur.rowcount
            #if self._cur.rowcount >= 0: 
            if self._rowcount() >= 0: 
                d = self._build_names()
                for i in self._cur.fetchall():
                    print 'list ' * 10, i
                    result.append(RowObject(i, d))
        except self._module.ProgrammingError, e:
            print 'ProgrammingError', e
        return result

    def format_ascii(self):
        def format_one_line(data, lens):
            return '| ' + ' | '.join(d.ljust(i) for i, d in zip(lens, data)) + ' |'
        def get_names(desc):
            return [d[0].lower() for d in self._cur.description]
        def get_names_len(desc):
            return [len(d[0]) for d in self._cur.description]
        def get_strings_and_lens(data, in_lens):
            lens = list(in_lens)
            strings = []
            for row in data:
                tmp = []
                for i, c in enumerate(row):
                    str_ = str(c)
                    lens[i] = max(lens[i], len(str_))
                    tmp.append(str_)
                strings.append(tmp)
            return strings, lens
        
        assert len(self._cur.description) > 0, "There are no result"
        lens = get_names_len(self._cur.description)
        strings, lens = get_strings_and_lens(self._cur.fetchall(), lens)
    
        result = []
        spacer = '+-' + '-+-'.join(['-' * i for i in lens]) + '-+'
        
        result.append(spacer)
        result.append(format_one_line(get_names(self._cur.description), lens))
        result.append(spacer)
        
        for data in strings:
            result.append(format_one_line(data, lens))
        result.append(spacer)
        
        return '\n'.join(result)


#--------------------------------------------------------------------
# Database specyfic code


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
     
    def _rowcount(self):
        return 1
        
    def insert_id(self, sql, data):
        self.execute(sql, data)
        rid = self.execute('SELECT last_insert_rowid()').list()[0][0]
        print rid
        return rid

    def _do_insert(self, table, values):
        sql, data = self._insert_build(table, values)
        self._just_execute(sql, data)
        rid = self.execute('SELECT last_insert_rowid()').list()[0][0]
        return rid

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

    #def insert_id(self, sql, data):
        #var = self._cur.var(self._module.NUMBER)
        ##self.execute(sql + ' RETURNING id INTO %s', data + [var])
        #self._cur.execute(sql + ' returning id into %s', data + [var])
        #return var.getvalue()
        
    def insert_id(self, sql, data):
        parts = sql.lower().split()
        assert parts[:2] == ['insert', 'into']
        self.execute(sql, data)
        rid = self.execute("SELECT %s_id_seq.curval FROM dual" % parts[2]).list()[0][0]
        return rid
    
    def _do_insert(self, table, values):
        rid = self.execute("SELECT %s_id_seq.nextval FROM dual" % table).list()[0][0]
        values = dict(values)
        values['id'] = rid
        sql, data = self._insert_build(table, values)
        self._just_execute(sql, data)
        return rid

class DB2(Database):
    """ easy_install ibm_db
    
    1) install DB2 9 Express-C

    2) download PyDB2-1.1.0-2.tar.gz
    http://sourceforge.net/projects/pydb2/

    3) tar zxvf PyDB2-1.1.0-2.tar.gz
    4) cd PyDB2-1.1.0
    5) vi setup.py
    6) modify 2 lines 

    DB2_ROOT = "/opt/ibm/db2exc/V9.5/"
    library_dirs=[db2_root_dir+'lib32'],

    7) sudo python setup.py install
    
    """
    _short_names = ['db2']
    _short_name  = 'db2'
    _full_name  = 'DB2'

    def __init__(self,  **config):
        Database.__init__(self, **config)

        if 'driver' not in config or config['driver'] in ['pydb2', None]:
            import DB2
            self._module = DB2
            # TODO: host and port
            args = Database._dict_copy(config, {'dbname': 'dsn', 'user': 'uid', 'password': 'pwd'})
            self._db = self._module.connect(**args)
        elif config['driver'] in ['ibm_db', 'ibmdb']:
            pass
        else:
            raise "Unknow driver %r" % driver

        self._cur = self._db.cursor()

    def schema_list(self, what='table'):
        what = what.lower()

        if what in ('table', 'tables'):
            self._cur.execute("SELECT name FROM sysibm.systables WHERE type = 'T' AND creator NOT LIKE 'SYS%' ORDER BY name")
            data = self._cur.fetchall()
        else:
            raise 'Unsupported'
        return [i[0].lower() for i in data]
    
    def _rowcount(self):
        return 1
    
    def _do_insert(self, table, values):
        sql, data = self._insert_build(table, values)
        self._just_execute(sql, data)
        # TODO: better last_insert_id 
        rid = (self.execute('SELECT max(id) from %s' % table).list() + [[0]])[0][0]
        return rid

class SQLServer(Database):
    """wajig install freetds-dev && easy_install pymssql
    
    """
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

    def insert_id(self, sql, data):
        self.execute(sql, data)
        rid = self.execute('SELECT last_insert_id()').list()[0][0]
        #rid = self.execute(sql + ' RETURNING id', data).list()[0][0]
        return rid

    def _do_insert(self, table, values):
        sql, data = self._insert_build(table, values)
        self._just_execute(sql, data)
        rid = self.execute('SELECT last_insert_id()').list()[0][0]
        return rid


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

    def insert_id(self, sql, data):
        rid = self.execute(sql + ' RETURNING id', data).list()[0][0]
        return rid
    
    def _do_insert(self, table, values):
        sql, data = self._insert_build(table, values, {'id': 'DEFAULT'})
        rid = self._just_execute(sql + ' RETURNING id', data).list()[0][0]
        return rid

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

def connect(file=None, dsn=None, **kw):
    """ Create connection to database.
        
        Read connection params from:
         1) file
         2) DSN string
         3) keyword params
        Parameters from next source can overwrite previous 
    """
    def param(data):
        parts = [i.strip() for i in data.split('=', 1)]
        assert len(parts) == 2
        name, value = parts[0], parts[1]
        if (value[0] == value[-1]) and (value[0] in ['"', "'"]):
            return {name: value[1:-1]}
        else:
            return {name: value}

    params = {}
    
    # read params from file
    if file is not None:
        fin = open(file)
        lines = fin.readlines()
        fin.close()
        for line in lines:
            line = line.strip()
            
            # skip empty lines and comments
            if line and not line.startswith('#'):
                params.update(param(line))
    
    # read params from DSN
    if dsn is not None:
        for part in dsn.split():
            params.update(param(part))
            
    params.update(kw)
    
    return Database.connect(**params)
    

def main():
    #db = Database.connect(dialect='postgresql', dbname='test_pada', user='kosqx', host='localhost', password='kos144')
    db = Database.connect(dialect='sqlite', dbname='abc.db')
    #db = Database.connect(dialect='oracle', dbname='xe', user='kosqx', password='kos144')
    #db = Database.connect(dialect='mysql', dbname='test_mvcc', user='kosqx', password='kos144')

    db.set_paramstyle('numeric')

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
    
    
    for i in db.execute({'*': "SELECT * FROM item WHERE value >= :1"}, [5.5]):
        print i.id, i.value

    print db.execute({'*': "SELECT * FROM item WHERE value >= :1"}, [5.5]).format_ascii()
        

def sql_split(sql):
    state = ""
    result = []
    tmp = []
    for i in sql:
        if state == "":
            if i == "'":
                state = "'"
                result.append(''.join(tmp))
                tmp = []
            else:
                tmp.append(i)
        if state == "'":
            if i == "'":
                state = "''"
            else:
                tmp.append(i)
                
        if state == "''":
            if i == "'":
                state = "'''"
                result.append(''.join(tmp))
            else:
                tmp.append(i)
        

if __name__ == '__main__':
    main()
    #test_speed()
    #unittest.main()
## driver, adapter, module

