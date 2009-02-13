# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Coherence backend presenting the content of the MIRO Guide catalog for on-line videos
#
# The APi is described on page:
# https://develop.participatoryculture.org/trac/democracy/wiki/MiroGuideApi

# Copyright 2009, Jean-Michel Sizun
# Copyright 2009 Frank Scholz <coherence@beebits.net>

from coherence.upnp.core import utils
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendStore,BackendItem

from coherence.backends.youtube_storage import Container, LazyContainer, VideoProxy

ROOT_CONTAINER_ID = 0
CATEGORIES_CONTAINER_ID = 101
LANGUAGES_CONTAINER_ID = 102


class VideoItem(BackendItem):

    def __init__(self, store, id, name, description, url, thumbnail_url, parent): #parent, id, external_id, title, url, mimetype, entry):
        self.parent = parent
        self.id = id
        self.name = name
        self.duration = None
        self.size = None
        self.mimetype = None
        self.thumbnail_url = thumbnail_url
        self.description = None
        self.date = None
        self.item = None
        self.store = store
        self.url = self.store.urlbase + str(self.id)
        self.location = VideoProxy(url, hash(url),
                                   store.proxy_mode,
                                   store.cache_directory, store.cache_maxsize, store.buffer_size
                                   )


    def get_item(self):
        if self.item == None:
            self.item = DIDLLite.VideoItem(self.id, self.parent.id, self.name)
            self.item.description = self.description
            self.item.date = self.date
            if self.thumbnail_url is not None:
                self.item.icon = self.thumbnail_url
            res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            res.duration = self.duration
            res.size = self.size
            self.item.res.append(res)
        return self.item

    def get_path(self):
        return self.url



class MiroCategory(LazyContainer):
    def __init__(self, id, store, parent_id, title, category_id):
        LazyContainer.__init__(self, id, store, parent_id, title)
        self.category_id = category_id
    def retrieve_children(self):
        return self.store.retrieveChannels (self, "category", self.category_id)

class MiroLanguage(LazyContainer):
    def __init__(self, id, store, parent_id, title, language_id):
        LazyContainer.__init__(self, id, store, parent_id, title)
        self.language_id = language_id
    def retrieve_children(self):
        return self.store.retrieveChannels (self, "language", self.language_id)

class MiroChannel(LazyContainer):
    def __init__(self, id, store, parent_id, title, channel_id):
        LazyContainer.__init__(self, id, store, parent_id, title)
        self.channel_id = channel_id
    def retrieve_children(self):
        return self.store.retrieveChannelItems (self, self.channel_id)



class MiroStore(BackendStore):

    logCategory = 'miro_store'

    implements = ['MediaServer']

    wmc_mapping = {'4': 1000}

    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','MiroGuide')

        self.proxy_mode = kwargs.get('proxy_mode', 'redirect')
        self.cache_directory = kwargs.get('cache_directory', None)
        self.cache_maxsize = kwargs.get('cache_maxsize', 100000000)
        self.buffer_size = kwargs.get('buffer_size', 2000000)

        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'

        self.server = server
        self.update_id = 0
        self.store = {}

        rootItem = Container(ROOT_CONTAINER_ID,self,-1, self.name)
        self.store[ROOT_CONTAINER_ID] = rootItem
        categoriesItem = Container(CATEGORIES_CONTAINER_ID,self,-1, "Channels by category")
        self.storeItem(rootItem, categoriesItem, CATEGORIES_CONTAINER_ID)
        languagesItems = Container(LANGUAGES_CONTAINER_ID,self,-1, "Channels by language")
        self.storeItem(rootItem, languagesItems, LANGUAGES_CONTAINER_ID)

        def gotError(error):
            print "ERROR: %s" % error

        def gotCategories(result):
            if result is None:
                print "Unable to retrieve list of categories"
                return
            data,header = result
            categories = eval(data) # FIXME add some checks to avoid code injection
            for category in categories:
                name = category['name'].encode('ascii', 'strict')
                category_url = category['url'].encode('ascii', 'strict')
                self.appendCategory(name, name, categoriesItem)

        categories_url = "https://www.miroguide.com/api/list_categories"
        d1 = utils.getPage(categories_url)
        d1.addCallbacks(gotCategories, gotError)

        def gotLanguages(result):
            if result is None:
                print "Unable to retrieve list of languages"
                return
            data,header = result
            languages = eval(data) # FIXME add some checks to avoid code injection
            for language in languages:
                name = language['name'].encode('ascii', 'strict')
                language_url = language['url'].encode('ascii', 'strict')
                self.appendLanguage(name, name, languagesItems)

        languages_url = "https://www.miroguide.com/api/list_languages"
        d2 = utils.getPage(languages_url)
        d2.addCallbacks(gotLanguages, gotError)

        self.init_completed()


    def __repr__(self):
        return str(self.__class__).split('.')[-1]


    def storeItem(self, parent, item, id):
        self.store[id] = item
        parent.add_child(item)


    def appendCategory( self, name, category_id, parent):
        id = self.getnextID()
        item = MiroCategory(id, self, parent.get_id(), name, category_id)
        self.storeItem(parent, item, id)

    def appendLanguage( self, name, language_id, parent):
        id = self.getnextID()
        item = MiroLanguage(id, self, parent.get_id(), name, language_id)
        self.storeItem(parent, item, id)

    def appendChannel(self, name, channel_id, parent):
        id = self.getnextID()
        item = MiroChannel(id, self, parent.get_id(), name, channel_id)
        self.storeItem(parent, item, id)

    def appendVideoEntry(self, name, description, url, thumbnail_url, parent):
        id = self.getnextID()
        item = VideoItem (self, id, name, description, url, thumbnail_url, parent)
        self.storeItem(parent, item, id)

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            return self.store[int(id)]
        except (ValueError,KeyError):
            pass
        return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None

        if self.server:
            self.server.connection_manager_server.set_variable(
               0, 'SourceProtocolInfo',
               ['http-get:*:%s:*' % 'video/'], #FIXME put list of all possible video mimetypes
               default=True)


    def retrieveChannels (self, parent, filter, filter_value):
        uri = "https://www.miroguide.com/api/get_channels?limit=100&filter=%s&filter_value=%s" % (filter, filter_value)
        print uri
        d = utils.getPage(uri)

        def gotChannels(result):
           if result is None:
               print "Unable to retrieve channel for category %s" % category_id
               return
           data,header = result
           channels = eval(data)
           for channel in channels:
               publisher = channel['publisher']
               description = channel['description']
               url = channel['url']
               hi_def = channel['hi_def']
               thumbnail_url = channel['thumbnail_url']
               postal_code = channel['postal_code']
               id = channel['id']
               website_url = channel['website_url']
               name = channel['name']
               self.appendChannel(name, id, parent)

        def gotError(error):
            print "ERROR: %s" % error

        d.addCallbacks(gotChannels, gotError)
        return d


    def retrieveChannelItems (self, parent, channel_id):
        uri = "https://www.miroguide.com/api/get_channel?id=%s" % channel_id
        d = utils.getPage(uri)

        def gotItems(result):
           if result is None:
               print "Unable to retrieve items for channel %s" % channel_id
               return
           data,header = result
           channel = eval(data)
           items = []
           if (channel.has_key('item')):
               items = channel['item']
           for item in items:
               url = item['url']
               description = item['description']
               name = item['name']
               thumbnail_url = None
               if (channel.has_key('thumbnail_url')):
                   thumbnail_url = channel['thumbnail_url']
               #size = size['size']
               self.appendVideoEntry(name, description, url, thumbnail_url, parent)

        def gotError(error):
            print "ERROR: %s" % error

        d.addCallbacks(gotItems, gotError)
        return d