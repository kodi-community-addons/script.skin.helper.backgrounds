#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    script.skin.helper.backgrounds
    a helper service for Kodi skins providing rotating backgrounds
'''

import thread
import random
import os
from datetime import timedelta
from utils import log_msg, log_exception, get_content_path, urlencode, ADDON_ID
import xbmc
import xbmcvfs
import xbmcaddon
import xbmcgui
from simplecache import use_cache, SimpleCache
from conditional_backgrounds import get_cond_background
from smartshortcuts import SmartShortCuts
from wallimages import WallImages
from artutils import KodiDb, get_clean_image


class BackgroundsUpdater():
    '''Background service providing rotating backgrounds to Kodi skins'''
    exit = False
    all_backgrounds = {}
    backgrounds_delay = 0
    walls_delay = 30
    all_backgrounds_keys = {}
    
    pvr_bg_recordingsonly = False
    custom_picturespath = ""

    def __init__(self):
        self.cache = SimpleCache()
        self.kodidb = KodiDb()
        self.win = xbmcgui.Window(10000)
        self.kodimonitor = xbmc.Monitor()
        self.all_backgrounds_labels = []
        self.smartshortcuts = SmartShortCuts(self.cache, self.win)
        self.wallimages = WallImages(self.win, self.get_images_from_vfspath)

    def stop(self):
        '''stop running our background service '''
        log_msg("BackgroundsUpdater - stop called", xbmc.LOGNOTICE)
        self.exit = True
        self.smartshortcuts.exit = True
        self.wallimages.exit = True
        del self.smartshortcuts
        del self.wallimages
        del self.win
        del self.kodimonitor

    def run(self):
        '''called to start our background service '''
        log_msg("BackgroundsUpdater - started", xbmc.LOGNOTICE)
        self.get_config()
        backgrounds_task_interval = 25
        walls_task_interval = 25
        delayed_task_interval = 112

        while not self.kodimonitor.abortRequested():

            # Process backgrounds only if we're not watching fullscreen video
            if xbmc.getCondVisibility(
                "![Window.IsActive(fullscreenvideo) | Window.IsActive(script.pseudotv.TVOverlay.xml) | "
                    "Window.IsActive(script.pseudotv.live.TVOverlay.xml)] | "
                    "Window.IsActive(script.pseudotv.live.EPG.xml)"):

                # background stuff like reading the skin settings and generating smart shortcuts
                if delayed_task_interval >= 120:
                    delayed_task_interval = 0
                    self.get_config()
                    self.smartshortcuts.build_smartshortcuts()

                # force refresh smart shortcuts on request
                if self.win.getProperty("refreshsmartshortcuts"):
                    self.win.clearProperty("refreshsmartshortcuts")
                    self.smartshortcuts.build_smartshortcuts()

                # Update home backgrounds every interval (if enabled by skinner)
                if self.backgrounds_delay and backgrounds_task_interval >= self.backgrounds_delay:
                    backgrounds_task_interval = 0
                    self.update_backgrounds()

                # Update wall images every interval (if enabled by skinner)
                if self.walls_delay and walls_task_interval >= self.walls_delay:
                    walls_task_interval = 0
                    self.wallimages.all_backgrounds_keys = self.all_backgrounds_keys
                    thread.start_new_thread(self.wallimages.update_wallbackgrounds, ())
                    self.wallimages.update_manualwalls()

            self.kodimonitor.waitForAbort(1)
            backgrounds_task_interval += 1
            walls_task_interval += 1
            delayed_task_interval += 1

        # abort requested
        self.stop()

    def get_config(self):
        '''gets various settings for the script as set by the skinner or user'''

        addon = xbmcaddon.Addon(ADDON_ID)
        # skinner (or user) enables the random fanart images by setting the randomfanartdelay skin string
        try:
            self.backgrounds_delay = int(xbmc.getInfoLabel("Skin.String(SkinHelper.RandomFanartDelay)"))
        except Exception:
            pass
        
        self.walls_delay = int(addon.getSetting("wallimages_delay"))
        self.wallimages.max_wallimages = int(addon.getSetting("max_wallimages"))
        self.pvr_bg_recordingsonly = addon.getSetting("pvr_bg_recordingsonly") == "true"
        if addon.getSetting("enable_custom_images_path") == "true":
            self.custom_picturespath = addon.getSetting("custom_images_path")
        else:
            self.custom_picturespath = ""
        del addon

        try:
            # skinner can enable manual wall images generation so check for these settings
            # store in memory so wo do not have to query the skin settings too often
            if self.walls_delay:
                for key in self.all_backgrounds_keys.iterkeys():
                    limitrange = xbmc.getInfoLabel("Skin.String(%s.EnableWallImages)" % key)
                    if limitrange:
                        self.wallimages.manual_walls[key] = int(limitrange)
        except Exception as exc:
            log_exception(__name__, exc)

    @use_cache(0.5)
    def get_images_from_vfspath(self, lib_path, limit=50):
        '''get all images from the given vfs path'''
        result = []
        # safety check: check if no library windows are active to prevent any addons setting the view
        if (xbmc.getCondVisibility("Window.IsMedia") and "plugin" in lib_path) or self.exit:
            return None  # return None so the cache is ignored

        lib_path = get_content_path(lib_path)
        if "plugin.video.emby" in lib_path and "browsecontent" in lib_path and "filter" not in lib_path:
            lib_path = lib_path + "&filter=random"

        for media in self.kodidb.files(lib_path, sort={"method": "random", "order": "descending"},
                                       limits=(0, limit)):
            image = {}

            if media['label'].lower() == "next page":
                continue
            if media.get('art'):
                if media['art'].get('fanart'):
                    image["fanart"] = get_clean_image(media['art']['fanart'])
                elif media['art'].get('tvshow.fanart'):
                    image["fanart"] = get_clean_image(media['art']['tvshow.fanart'])
                if media['art'].get('thumb'):
                    image["thumbnail"] = get_clean_image(media['art']['thumb'])
            if not image.get('fanart') and media.get("fanart"):
                image["fanart"] = get_clean_image(media['fanart'])
            if not image.get("thumbnail") and media.get("thumbnail"):
                image["thumbnail"] = get_clean_image(media["thumbnail"])

            # only append items which have a fanart image
            if image.get("fanart"):
                # also append other art to the dict
                image["title"] = media.get('title', '')
                if not image.get("title"):
                    image["title"] = media.get('label', '')
                image["landscape"] = get_clean_image(media.get('art', {}).get('landscape', ''))
                image["poster"] = get_clean_image(media.get('art', {}).get('poster', ''))
                image["clearlogo"] = get_clean_image(media.get('art', {}).get('clearlogo', ''))
                result.append(image)
        return result

    def get_pictures(self):
        '''get images we can use as pictures background'''
        images = []
        # try cache first
        cachestr = "SkinHelper.PictureBackgrounds"
        cache = self.cache.get(cachestr, checksum=self.custom_picturespath)
        if cache:
            return cache
        # load the pictures from the custom path or from all picture sources
        if self.custom_picturespath:
            # load images from custom path
            files = xbmcvfs.listdir(self.custom_picturespath)[1]
            # pick max 50 images from path
            for file in files[:50]:
                if file.lower().endswith(".jpg") or file.lower().endswith(".png"):
                    image = os.path.join(self.custom_picturespath, file.decode("utf-8"))
                    images.append({"fanart": image, "title": file.decode("utf-8")})
        else:
            # load pictures from all picture sources
            media_array = self.kodidb.get_json('Files.GetSources', optparam=("media", "pictures"))
            randomdirs = []
            for source in media_array:
                if 'file' in source:
                    if "plugin://" not in source["file"]:
                        dirs = xbmcvfs.listdir(source["file"])[0]
                        if dirs:
                            # pick 10 random subdirectories
                            while not (len(randomdirs) == 10 or len(randomdirs) == len(dirs)):
                                randomdir = os.path.join(source["file"], random.choice(dirs).decode("utf-8"))
                                if randomdir not in randomdirs:
                                    randomdirs.append(randomdir)

                        # append root to dirs so we can also list images in the root
                        randomdirs.append(source["file"])

                        # pick 15 images from each dir
                        for item in randomdirs:
                            files2 = xbmcvfs.listdir(item)[1]
                            count = 0
                            for count, filename in enumerate(files2):
                                if (filename.endswith(".jpg") or filename.endswith(".png")) and count < 15:
                                    filename = filename.decode("utf-8")
                                    image = os.path.join(item, filename)
                                    images.append({"fanart": image, "title": filename})

        # store images in the cache
        self.cache.set(cachestr, images, checksum=self.custom_picturespath, expiration=timedelta(days=3))
        return images

    @use_cache(1)
    def get_global_background(self, keys):
        '''get backgrounds from multiple other collections'''
        images = []
        for key in keys:
            if key in self.all_backgrounds_keys:
                imgs = self.get_images_from_vfspath(self.all_backgrounds_keys[key])
                if imgs:
                    images += imgs
        return images

    def set_background(self, win_prop, lib_path, images=None, fallback_image="", label=None):
        '''set the window property for the background image'''
        if not images and lib_path:
            images = self.get_images_from_vfspath(lib_path)
            if win_prop not in self.all_backgrounds_keys:
                self.all_backgrounds_keys[win_prop] = lib_path
        if images:
            image = random.choice(images)
            for key, value in image.iteritems():
                if key == "fanart":
                    self.win.setProperty(win_prop, value)
                else:
                    self.win.setProperty("%s.%s" % (win_prop, key), value)
        else:
            self.win.setProperty(win_prop, fallback_image)
        # store the label of the background for later exchange with skinshortcuts
        if not any(win_prop in item for item in self.all_backgrounds_labels):
            if label and isinstance(label, int):
                label = xbmc.getInfoLabel("$ADDON[%s %s]" % (ADDON_ID, label))
            elif not label:
                label = win_prop
            self.all_backgrounds_labels.append( (win_prop, label) )
            self.win.setProperty("SkinHelper.AllBackgrounds", repr(self.all_backgrounds_labels))
            self.win.setProperty("%s.label" % win_prop, label)

    def set_global_background(self, win_prop, keys, label=None):
        '''set random background from multiple other collections'''
        images = self.get_global_background(keys)
        self.set_background(win_prop, "", images, label=label)

    def update_backgrounds(self):
        '''update all our provided backgrounds'''

        # conditional background
        self.win.setProperty("SkinHelper.ConditionalBackground", get_cond_background() )

        # movies backgrounds
        if xbmc.getCondVisibility("Library.HasContent(movies)"):
            # random/all movies
            self.set_background("SkinHelper.AllMoviesBackground", "videodb://movies/titles/", label=32010)
            # in progress movies
            self.set_background(
                "SkinHelper.InProgressMoviesBackground",
                "videodb://movies/titles/?xsp=%s" %
                urlencode(
                    '{"limit":50,"order":{"direction":"ascending","method":"random"},'
                    '"rules":{"and":[{"field":"inprogress","operator":"true","value":[]}]},"type":"movies"}'),
                label=32012)
            # recent movies
            self.set_background("SkinHelper.RecentMoviesBackground", "videodb://recentlyaddedmovies/", label=32011)
            # unwatched movies
            self.set_background(
                "SkinHelper.UnwatchedMoviesBackground",
                "videodb://movies/titles/?xsp=%s" %
                urlencode(
                    '{"limit":50,"order":{"direction":"ascending","method":"random"},'
                    '"rules":{"and":[{"field":"playcount","operator":"is","value":0}]},"type":"movies"}'), label=32013)

        # tvshows backgrounds
        if xbmc.getCondVisibility("Library.HasContent(tvshows)"):
            # random/all tvshows
            self.set_background("SkinHelper.AllTvShowsBackground", "videodb://tvshows/titles/", label=32014)
            # in progress tv shows
            self.set_background(
                "SkinHelper.InProgressShowsBackground",
                "videodb://tvshows/titles/?xsp=%s" %
                urlencode(
                    '{"limit":50,"order":{"direction":"ascending","method":"random"},'
                    '"rules":{"and":[{"field":"inprogress","operator":"true","value":[]}]},"type":"tvshows"}'),
                label=32016)
            # recent episodes
            self.set_background("SkinHelper.RecentEpisodesBackground", "videodb://recentlyaddedepisodes/", label=32015)

        # all musicvideos
        if xbmc.getCondVisibility("Library.HasContent(musicvideos)"):
            self.set_background("SkinHelper.AllMusicVideosBackground", "videodb://musicvideos/titles", label=32018)

        # all music
        if xbmc.getCondVisibility("Library.HasContent(music)"):
            # music artists
            self.set_background("SkinHelper.AllMusicBackground", "musicdb://artists/", label=32019)
            # random songs
            self.set_background(
                "SkinHelper.AllMusicSongsBackground",
                "plugin://script.skin.helper.widgets/?mediatype=songs&action=random&limit=50",
                label=32022)
            # recent albums
            self.set_background(
                "SkinHelper.RecentMusicBackground",
                "plugin://script.skin.helper.widgets/?mediatype=albums&action=recent&limit=50",
                label=32023)

        # tmdb backgrounds (extendedinfo)
        if xbmc.getCondVisibility("System.HasAddon(script.extendedinfo)"):
            self.set_background(
                "SkinHelper.TopRatedMovies",
                "plugin://script.extendedinfo/?info=topratedmovies",
                label=32020)
            self.set_background(
                "SkinHelper.TopRatedShows",
                "plugin://script.extendedinfo/?info=topratedtvshows",
                label=32021)

        # pictures background
        self.set_background("SkinHelper.PicturesBackground", "", self.get_pictures(), label=32017)

        # pvr background
        if xbmc.getCondVisibility("PVR.HasTvChannels"):
            images = self.get_images_from_vfspath(
                "plugin://script.skin.helper.widgets/?mediatype=pvr&action=recordings&limit=50")
            if not self.pvr_bg_recordingsonly:
                tv_images = self.get_images_from_vfspath(
                    "plugin://script.skin.helper.widgets/?mediatype=pvr&action=channels&limit=25")
                if not images and tv_images:
                    images = tv_images
                elif images and tv_images:
                    images += tv_images
            if images:  # check if images not empty because cache returns None instead of list on failures
                self.set_background("SkinHelper.PvrBackground", "", images, label=32024)

        # smartshortcuts backgrounds
        for node in self.smartshortcuts.get_smartshortcuts_nodes():
            self.set_background(node[0], node[1], label=node[2])

        # global backgrounds
        self.set_global_background("SkinHelper.GlobalFanartBackground",
                                   ["SkinHelper.AllMoviesBackground", "SkinHelper.AllTvShowsBackground",
                                    "SkinHelper.AllMusicVideosBackground", "SkinHelper.AllMusicBackground"],
                                   label=32009)
        self.set_global_background("SkinHelper.AllVideosBackground",
                                   ["SkinHelper.AllMoviesBackground", "SkinHelper.AllTvShowsBackground",
                                    "SkinHelper.AllMusicVideosBackground"], label=32025)
        self.set_global_background(
            "SkinHelper.AllVideosBackground2", [
                "SkinHelper.AllMoviesBackground", "SkinHelper.AllTvShowsBackground"], label=32026)
        self.set_global_background(
            "SkinHelper.RecentVideosBackground",
            ["SkinHelper.RecentMoviesBackground", "SkinHelper.RecentEpisodesBackground"], label=32027)
        self.set_global_background(
            "SkinHelper.InProgressVideosBackground",
            ["SkinHelper.InProgressMoviesBackground", "SkinHelper.InProgressShowsBackground"], label=32028)
