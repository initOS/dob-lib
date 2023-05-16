# -*- coding: utf-8 -*-

def migrate(env, db_version):
    env.check(str(db_version))
