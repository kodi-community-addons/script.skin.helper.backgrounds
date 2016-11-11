#!/usr/bin/python
# -*- coding: utf-8 -*-
from utils import get_content_path, log_msg, log_exception, ADDON_ID
from artutils import detect_plugin_content, KodiDb
from simplecache import use_cache
import xbmc
import xbmcvfs
import thread


class SmartShortCuts():
    '''Smart shortcuts listings'''
    exit = False
    all_nodes = {}
    toplevel_nodes = []
    build_busy = False

    def __init__(self, cache, win):
        self.cache = cache
        self.win = win

    def get_smartshortcuts_nodes(self):
        '''return all smartshortcuts paths for which an image should be generated'''
        nodes = []
        for value in self.all_nodes.itervalues():
            nodes += value
        return nodes

    def build_smartshortcuts(self):
        '''build all smart shortcuts nodes - only proceed if build is not already in process'''
        if self.exit or self.build_busy:
            return
        else:
            build_busy = True
            # build all smart shortcuts nodes
            thread.start_new_thread(self.plex_nodes, ())
            thread.start_new_thread(self.netflix_nodes, ())
            self.emby_nodes()
            self.playlists_nodes()
            self.favourites_nodes()
            # set all toplevel nodes in window prop for exchange with skinshortcuts
            self.win.setProperty("all_smartshortcuts", repr(self.toplevel_nodes))
            self.build_busy = False

    def emby_nodes(self):
        '''build smart shortcuts for the emby addon'''
        if not self.all_nodes.get("emby"):
            nodes = []
            if xbmc.getCondVisibility("System.HasAddon(plugin.video.emby) + Skin.HasSetting(SmartShortcuts.emby)"):
                emby_property = self.win.getProperty("emby.nodes.total")
                if emby_property:
                    content_strings = ["", ".recent", ".inprogress", ".unwatched", ".recentepisodes",
                                       ".inprogressepisodes", ".nextepisodes", "recommended"]
                    nodes = []
                    total_nodes = int(emby_property)
                    for count in range(total_nodes):
                        # stop if shutdown requested in the meanwhile
                        if self.exit:
                            return
                        for content_string in content_strings:
                            key = "emby.nodes.%s%s" % (count, content_string)
                            item_path = self.win.getProperty("emby.nodes.%s%s.path" % (count, content_string))
                            label = self.win.getProperty("emby.nodes.%s%s.title" % (count, content_string))
                            if item_path:
                                content = get_content_path(item_path)
                                nodes.append(("%s.image" % key, item_path, label))
                                if content_string == "":
                                    if "emby.nodes.%s" % count not in self.toplevel_nodes:
                                        self.toplevel_nodes.append("emby.nodes.%s" % count)
                                    self.create_smartshortcuts_submenu(
                                        "emby.nodes.%s" % count, "special://home/addons/plugin.video.emby/icon.png")
                log_msg("Generated smart shortcuts for emby nodes: %s" % nodes)
                self.all_nodes["emby"] = nodes

    def plex_nodes(self):
        '''build smart shortcuts listing for the (legacy) plex addon'''
        if not self.all_nodes.get("plex"):
            nodes = []
            if xbmc.getCondVisibility("System.HasAddon(plugin.video.plexbmc) + Skin.HasSetting(SmartShortcuts.plex)"):
                xbmc.executebuiltin('RunScript(plugin.video.plexbmc,amberskin)')
                # wait a few seconds for the initialization to be finished
                monitor = xbmc.Monitor()
                monitor.waitForAbort(5)
                del monitor

                # get the plex setting if there are subnodes
                plexaddon = xbmcaddon.Addon(id='plugin.video.plexbmc')
                secondary_menus = plexaddon.getSetting("secondary") == "true"
                del plexaddon

                content_strings = ["", ".ondeck", ".recent", ".unwatched"]
                total_nodes = 50
                for i in range(total_nodes):
                    if not self.win.getProperty("plexbmc.%s.title" % i) or self.exit:
                        break
                    for content_string in content_strings:
                        key = "plexbmc.%s%s" % (i, content_string)
                        label = self.win.getProperty("plexbmc.%s.title" % i).decode("utf-8")
                        media_type = self.win.getProperty("plexbmc.%s.type" % i).decode("utf-8")
                        if media_type == "movie":
                            media_type = "movies"
                        if secondary_menus:
                            item_path = self.win.getProperty("plexbmc.%s.all" % i).decode("utf-8")
                        else:
                            item_path = self.win.getProperty("plexbmc.%s.path" % i).decode("utf-8")
                        item_path = item_path.replace("VideoLibrary", "Videos")  # fix for krypton ?
                        alllink = item_path
                        alllink = alllink.replace("mode=1", "mode=0")
                        alllink = alllink.replace("mode=2", "mode=0")
                        if content_string == ".recent":
                            label += " - Recently Added"
                            if media_type == "show":
                                media_type = "episodes"
                            if secondary_menus:
                                item_path = self.win.getProperty(key).decode("utf-8")
                            else:
                                item_path = alllink.replace("/all", "/recentlyAdded")
                        elif content_string == ".ondeck":
                            label += " - On deck"
                            if media_type == "show":
                                media_type = "episodes"
                            if secondary_menus:
                                item_path = self.win.getProperty(key).decode("utf-8")
                            else:
                                item_path = alllink.replace("/all", "/onDeck")
                        elif content_string == ".unwatched":
                            if media_type == "show":
                                media_type = "episodes"
                            label += " - Unwatched"
                            item_path = alllink.replace("/all", "/unwatched")
                        elif content_string == "":
                            if media_type == "show":
                                media_type = "tvshows"
                            if key not in self.toplevel_nodes:
                                self.toplevel_nodes.append(key)
                            self.create_smartshortcuts_submenu("plexbmc.%s" % i,
                                                               "special://home/addons/plugin.video.plexbmc/icon.png")

                        # append media_type to path
                        if "&" in item_path:
                            item_path = item_path + "&media_type=" + media_type
                        else:
                            item_path = item_path + "?media_type=" + media_type
                        content = get_content_path(item_path)
                        nodes.append(("%s.image" % key, content, label))

                        # set smart shortcuts window props
                        self.win.setProperty("%s.label" % key, label)
                        self.win.setProperty("%s.title" % key, label)
                        self.win.setProperty("%s.action" % key, item_path)
                        self.win.setProperty("%s.path" % key, item_path)
                        self.win.setProperty("%s.content" % key, content)
                        self.win.setProperty("%s.type" % key, media_type)

                # add plex channels as entry
                # extract path from one of the nodes as a workaround because main plex
                # addon channels listing is in error
                if nodes:
                    item_path = self.win.getProperty("plexbmc.0.path").decode("utf-8")
                    if not item_path:
                        item_path = self.win.getProperty("plexbmc.0.all").decode("utf-8")
                    item_path = item_path.split("/library/")[0]
                    item_path = item_path + "/channels/all&mode=21"
                    item_path = item_path + ", return)"
                    key = "plexbmc.channels"
                    label = "Channels"
                    content = get_content_path(item_path)
                    nodes.append(("%s.image" % key, content, label))
                    self.win.setProperty("%s.label" % key, label)
                    self.win.setProperty("%s.title" % key, label)
                    self.win.setProperty("%s.action" % key, item_path)
                    self.win.setProperty("%s.path" % key, item_path)
                    self.win.setProperty("%s.content" % key, content)
                    self.win.setProperty("%s.type" % key, "episodes")
                    if key not in self.toplevel_nodes:
                        self.toplevel_nodes.append(key)
                self.all_nodes["plex"] = nodes

    def playlists_nodes(self):
        '''build smart shortcuts listing for playlists'''
        nodes = []
        if xbmc.getCondVisibility("Skin.HasSetting(SmartShortcuts.playlists)"):
            # build node listing
            import xml.etree.ElementTree as xmltree
            paths = [('special://videoplaylists/', 'Videos'), ('special://musicplaylists/', 'Music')]
            for playlistpath in paths:
                if xbmcvfs.exists(playlistpath[0]):
                    media_array = KodiDb().files(playlistpath[0])
                    for count, item in enumerate(media_array):
                        try:
                            label = ""
                            if item["file"].endswith(".xsp") and "Emby" not in item["file"]:
                                playlist = item["file"]
                                contents = xbmcvfs.File(playlist, 'r')
                                contents_data = contents.read()
                                contents.close()
                                xmldata = xmltree.fromstring(contents_data)
                                media_type = "unknown"
                                label = item["label"]
                                for line in xmldata.getiterator():
                                    if line.tag == "smartplaylist":
                                        media_type = line.attrib['type']
                                    if line.tag == "name":
                                        label = line.text
                                key = "playlist.%s" % count
                                item_path = "ActivateWindow(%s,%s,return)" % (playlistpath[1], playlist)
                                self.win.setProperty("%s.label" % key, label)
                                self.win.setProperty("%s.title" % key, label)
                                self.win.setProperty("%s.action" % key, item_path)
                                self.win.setProperty("%s.path" % key, item_path)
                                self.win.setProperty("%s.content" % key, playlist)
                                self.win.setProperty("%s.type" % key, media_type)
                                nodes.append(("%s.image" % key, playlist, label))
                                if key not in self.toplevel_nodes:
                                    self.toplevel_nodes.append(key)
                        except Exception:
                            log_msg("Error while processing smart shortcuts for playlist %s  --> "
                                    "This file seems to be corrupted, please remove it from your system "
                                    "to prevent any further errors." % item["file"], xbmc.LOGWARNING)
            self.all_nodes["playlists"] = nodes

    def favourites_nodes(self):
        '''build smart shortcuts for favourites'''
        if xbmc.getCondVisibility("Skin.HasSetting(SmartShortcuts.favorites)"):
            # build node listing
            nodes = []
            favs = KodiDb().favourites()
            for count, fav in enumerate(favs):
                if fav.get("windowparameter"):
                    content = fav["windowparameter"]
                    # check if this is a valid path with content
                    if ("script://" not in content.lower() and
                            "mode=9" not in content.lower() and
                            "search" not in content.lower() and
                            "play" not in content.lower()):
                        item_path = "ActivateWindow(%s,%s,return)" % (fav["window"], content)
                        if "&" in content and "?" in content and "=" in content and not content.endswith("/"):
                            content += "&widget=true"
                        media_type = detect_plugin_content(content)
                        if media_type:
                            key = "favorite.%s" % count
                            self.win.setProperty("%s.label" % key, fav["label"])
                            self.win.setProperty("%s.title" % key, fav["label"])
                            self.win.setProperty("%s.action" % key, item_path)
                            self.win.setProperty("%s.path" % key, item_path)
                            self.win.setProperty("%s.content" % key, content)
                            self.win.setProperty("%s.type" % key, media_type)
                            if key not in self.toplevel_nodes:
                                self.toplevel_nodes.append(key)
                            nodes.append(("%s.image" % key, content, fav["label"]))
            self.all_nodes["favourites"] = nodes

    def netflix_nodes(self):
        '''build smart shortcuts for the flix2kodi addon'''
        if not self.all_nodes.get("netflix"):
            if xbmc.getCondVisibility(
                    "System.HasAddon(plugin.video.flix2kodi) + Skin.HasSetting(SmartShortcuts.netflix)"):
                nodes = []
                f2k_addon = xbmcaddon.Addon('plugin.video.flix2kodi')
                profilename = f2k_addon.getSetting('profile_name').decode("utf-8")

                if profilename and f2k_addon.getSetting("username") and f2k_addon.getSetting("authorization_url"):
                    log_msg("Generating netflix entries for profile %s .... " % profilename)
                    # generic netflix shortcut
                    key = "netflix.generic"
                    label = f2k_addon.getAddonInfo('name')
                    content = "plugin://plugin.video.flix2kodi/?mode=main&widget=true&url&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    imagesitem_path = "plugin://plugin.video.flix2kodi/?mode="\
                        "list_videos&thumb&media_type=both&url=list%3f%26mylist&widget=true"
                    media_type = "media"
                    nodes.append((key, label, content, media_type, path, imagespath))
                    self.create_smartshortcuts_submenu("netflix.generic",
                                                       "special://home/addons/plugin.video.flix2kodi/icon.png")

                    # generic netflix mylist
                    key = "netflix.generic.mylist"
                    label = f2k_addon.getLocalizedString(30104)
                    content = "plugin://plugin.video.flix2kodi/?mode=list_videos"\
                        "&thumb&media_type=both&url=list%3f%26mylist&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    media_type = "movies"
                    nodes.append((key, label, content, media_type, path))

                    if self.exit:
                        return

                    # get mylist items...
                    mylist = []
                    media_array = kodi_json(
                        'Files.GetDirectory',
                        {
                            "properties": ["title"],
                            "directory": "plugin://plugin.video.flix2kodi/?mode=list_videos"
                            "&thumb&media_type=both&url=list%3f%26mylist&widget=true",
                            "media": "files",
                            "limits": {
                                "end": 50}})
                    for item in media_array:
                        mylist.append(item["label"])

                    # get dynamic entries...
                    media_array = kodi_json(
                        'Files.GetDirectory',
                        {"properties": ["title"],
                         "directory": "plugin://plugin.video.flix2kodi/?mode=main&media_type=dynamic&widget=true",
                         "media": "files", "limits": {"end": 50}})
                    if not media_array:
                        # if no result the plugin is in error, exit processing
                        return []
                    itemscount = 0
                    suggestions_node_found = False
                    for item in media_array:
                        if self.exit:
                            return
                        if ("list_viewing_activity" in item["file"]) or (
                                "mode=search" in item["file"]) or ("mylist" in item["file"]):
                            continue
                        elif profilename in item["label"] and not suggestions_node_found:
                            # this is the suggestions node!
                            suggestions_node_found = True
                            # generic suggestions node
                            key = "netflix.generic.suggestions"
                            content = item["file"] + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                            # movies suggestions node
                            key = "netflix.movies.suggestions"
                            new_item_path = item["file"].replace("media_type=both", "media_type=movie")
                            content = new_item_path + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                            # tvshows suggestions node
                            key = "netflix.tvshows.suggestions"
                            new_item_path = item["file"].replace("media_type=both", "media_type=show")
                            content = new_item_path + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "tvshows", path))
                        elif profilename in item["label"] and suggestions_node_found:
                            # this is the continue watching node!
                            # generic inprogress node
                            key = "netflix.generic.inprogress"
                            content = item["file"] + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                            # movies inprogress node
                            key = "netflix.movies.inprogress"
                            new_item_path = item["file"].replace("media_type=both", "media_type=movie")
                            content = new_item_path + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                            # tvshows inprogress node
                            key = "netflix.tvshows.inprogress"
                            new_item_path = item["file"].replace("media_type=both", "media_type=show")
                            content = new_item_path + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "tvshows", path))
                        elif item["label"].lower().endswith("releases"):
                            # this is the recent node!
                            # generic recent node
                            key = "netflix.generic.recent"
                            content = item["file"] + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                            # movies recent node
                            key = "netflix.movies.recent"
                            new_item_path = item["file"].replace("media_type=both", "media_type=movie")
                            content = new_item_path + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                            # tvshows recent node
                            key = "netflix.tvshows.recent"
                            new_item_path = item["file"].replace("media_type=both", "media_type=show")
                            content = new_item_path + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "tvshows", path))
                        elif item["label"] == "Trending":
                            # this is the trending node!
                            key = "netflix.generic.trending"
                            content = item["file"] + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            nodes.append((key, item["label"], content, "movies", path))
                        else:
                            key = "netflix.generic.suggestions.%s" % itemscount
                            content = item["file"] + "&widget=true"
                            item_path = "ActivateWindow(Videos,%s,return)" % content
                            media_type = "movies"
                            nodes.append((key, item["label"], content, media_type, path))
                            itemscount += 1

                        # get recommended node...
                        for mylist_item in mylist:
                            if mylist_item in item["label"]:
                                key = "netflix.generic.recommended"
                                content = item["file"] + "&widget=true"
                                item_path = "ActivateWindow(Videos,%s,return)" % item["file"]
                                nodes.append((key, item["label"], content, "movies", path))

                    # netflix movies
                    key = "netflix.movies"
                    label = f2k_addon.getAddonInfo('name') + " " + f2k_addon.getLocalizedString(30100)
                    content = "plugin://plugin.video.flix2kodi/?mode=main&thumb&media_type=movie&url&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    imagesitem_path = "plugin://plugin.video.flix2kodi/?mode=list_videos&thumb"\
                        "&media_type=movie&url=list%3f%26mylist&widget=true"
                    media_type = "movies"
                    nodes.append((key, label, content, media_type, path, imagespath))
                    self.create_smartshortcuts_submenu("netflix.movies",
                                                       "special://home/addons/plugin.video.flix2kodi/icon.png")

                    # netflix movies mylist
                    key = "netflix.movies.inprogress"
                    label = f2k_addon.getLocalizedString(30100) + " - " + f2k_addon.getLocalizedString(30104)
                    content = "plugin://plugin.video.flix2kodi/?mode=list_videos&thumb"\
                        "&media_type=movie&url=list%3f%26mylist&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    media_type = "movies"
                    nodes.append((key, label, content, media_type, path))

                    # netflix movies genres
                    key = "netflix.movies.genres"
                    label = f2k_addon.getLocalizedString(30100) + " - " + f2k_addon.getLocalizedString(30108)
                    content = "plugin://plugin.video.flix2kodi/?mode=list_genres&thumb"\
                        "&media_type=movie&url&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    media_type = "genres"
                    nodes.append((key, label, content, media_type, path))

                    # netflix tvshows
                    key = "netflix.tvshows"
                    label = f2k_addon.getAddonInfo('name') + " " + f2k_addon.getLocalizedString(30101)
                    content = "plugin://plugin.video.flix2kodi/?mode=main&thumb&media_type=show&url&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    imagesitem_path = "plugin://plugin.video.flix2kodi/?mode=list_videos&thumb"\
                        "&media_type=show&url=list%3f%26mylist&widget=true"
                    media_type = "tvshows"
                    nodes.append((key, label, content, media_type, path, imagespath))
                    self.create_smartshortcuts_submenu("netflix.tvshows",
                                                       "special://home/addons/plugin.video.flix2kodi/icon.png")

                    # netflix tvshows mylist
                    key = "netflix.tvshows.inprogress"
                    label = f2k_addon.getLocalizedString(30101) + " - " + f2k_addon.getLocalizedString(30104)
                    content = "plugin://plugin.video.flix2kodi/?mode=list_videos&thumb"\
                        "&media_type=show&url=list%3f%26mylist&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    media_type = "tvshows"
                    nodes.append((key, label, content, media_type, path))

                    # netflix tvshows genres
                    key = "netflix.tvshows.genres"
                    label = f2k_addon.getLocalizedString(30101) + " - " + f2k_addon.getLocalizedString(30108)
                    content = "plugin://plugin.video.flix2kodi/?mode=list_genres&thumb&media_type=show&url&widget=true"
                    item_path = "ActivateWindow(Videos,%s,return)" % content
                    media_type = "genres"
                    nodes.append((key, label, content, media_type, path))

                    if "netflix.generic" not in self.smartShortcuts["allSmartShortcuts"]:
                        self.smartShortcuts["allSmartShortcuts"].append("netflix.generic")
                    if "netflix.generic.movies" not in self.smartShortcuts["allSmartShortcuts"]:
                        self.smartShortcuts["allSmartShortcuts"].append("netflix.movies")
                    if "netflix.generic.tvshows" not in self.smartShortcuts["allSmartShortcuts"]:
                        self.smartShortcuts["allSmartShortcuts"].append("netflix.tvshows")

                    log_msg("DONE Generating netflix entries --> %s" % repr(nodes))
                    del f2k_addon

                    # set window props and set clean list of props in memory
                    newnodes = []
                    for node in nodes:
                        key = node[0]
                        self.win.setProperty(key + ".title", node[1])
                        self.win.setProperty(key + ".label", node[1])
                        self.win.setProperty(key + ".content", node[2])
                        self.win.setProperty(key + ".path", node[4])
                        self.win.setProperty(key + ".action", node[4])
                        self.win.setProperty(key + ".type", node[3])
                        if len(node) < 6:
                            newnodes.append("%s.image" % key, node[2], node[1])
                        else:
                            self.win.setProperty(key + ".image", node[5])
                    self.all_nodes["netflix"] = newnodes
                else:
                    log_msg("SKIP Generating netflix entries - addon is not ready!")

    @staticmethod
    def create_smartshortcuts_submenu(win_prop, icon_image):
        '''helper to create a skinshortcuts submenu for the top level smart shortcut node'''
        try:
            if xbmcvfs.exists("special://skin/shortcuts/"):
                shortcutsfile = "special://home/addons/script.skinshortcuts/resources/shortcuts/"\
                    "info-window-home-property-%s-title.DATA.xml" % win_prop.replace(".", "-")
                templatefile = "special://home/addons/%s/resources/smartshortcuts/smartshortcuts-submenu-template.xml" \
                    % (ADDON_ID)
                # read template file
                templatefile = xbmcvfs.File(templatefile)
                data = templatefile.read()
                templatefile.close()
                # write shortcuts file
                shortcutsfile = xbmcvfs.File(shortcutsfile, "w")
                data = data.replace("WINDOWPROP", win_prop)
                data = data.replace("ICONIMAGE", icon_image)
                shortcutsfile.write(data)
                shortcutsfile.close()
        except Exception as e:
            log_exception(__name__, e)
