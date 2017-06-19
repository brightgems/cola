#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Copyright (c) 2013 Qin Xuye <qin@qinxuye.me>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Created on 2013-6-9

@author: Chine
'''

from cola.core.errors import DependencyNotInstalledError

from conf import mongo_host, mongo_port, db_name, shard_key

try:
    from mongoengine import connect, Document, EmbeddedDocument, \
                            DoesNotExist, Q, \
                            StringField, DateTimeField, EmailField, \
                            BooleanField, URLField, IntField, FloatField, \
                            ListField, EmbeddedDocumentField, \
                            ValidationError
except ImportError:
    raise DependencyNotInstalledError('mongoengine')

connect(db_name, host=mongo_host, port=mongo_port)

DoesNotExist = DoesNotExist
Q = Q
ValidationError = ValidationError

class DoubanMovie(Document):
    sid = StringField(required=True)
    
    title = StringField()
    original_title = StringField()
    aka = ListField(StringField(max_length=500))
    tags = ListField(StringField(max_length=50))
    alt = URLField()
    rating = FloatField()
    high_rating_pct = FloatField()
    low_rating_pct = FloatField()
    ratings_count = IntField()
    reviews_count = IntField()
    wish_count = IntField()
    collect_count = IntField()
    directors = ListField(StringField())
    casts = ListField(StringField())
    writers = ListField(StringField())
    year = IntField()
    language = StringField()
    durations = IntField()
    genres = ListField(StringField())
    country = StringField()
    summary = StringField()
    pubdate = DateTimeField()
    seasons_count = IntField()
    current_season = IntField()
    episodes_count = IntField()
    photo_alt = URLField()
    subtype = StringField(max_length=1) # tv/movie
    imdb_id = StringField()
    last_update = DateTimeField()
    meta = {
        'indexes': [{'fields': ['id']}],
        'shard_key': shard_key
    }
