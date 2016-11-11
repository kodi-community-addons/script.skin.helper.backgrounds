#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    The service provides pre-built image walls for certain collections.
    Ready to use in your skin. The walls are pregenerated once and stored within the addon_data folder.
    NOTE: In the addon settings users can configure the rotation speed/interval or even disable the entire service.
    Default is 60 seconds.
'''

from utils import log_msg, ADDON_ID
from artutils import process_method_on_list, get_clean_image
import xbmc
import xbmcvfs
import random
from PIL import Image
import io

WALLS_PATH = "special://profile/addon_data/script.skin.helper.backgrounds/wall_backgrounds/"


class WallImages():
    '''Generate wall images from collection of images'''
    exit = False
    build_busy = {}
    max_wallimages = 20
    all_wall_images = {}
    manual_walls = {}
    all_backgrounds_keys = {}
    has_pil = True

    def __init__(self, win, get_images_from_path):
        self.win = win
        self.get_images_from_path = get_images_from_path

        # PIL fails on FTV devices ?
        try:
            img = Image.new("RGB", (1, 1))
            del img
        except Exception:
            self.has_pil = False
            log_msg("Wall backgrounds disabled - PIL is not supported on this device!", xbmc.LOGWARNING)

    def update_wallbackgrounds(self):
        '''generates wall images from collection of images from the library'''
        if self.max_wallimages:
            walls = []
            walls.append(("SkinHelper.AllMoviesBackground.Wall", "SkinHelper.AllMoviesBackground", "fanart"))
            walls.append(("SkinHelper.AllMoviesBackground.Poster.Wall", "SkinHelper.AllMoviesBackground", "poster"))
            walls.append(("SkinHelper.AllMusicBackground.Wall", "SkinHelper.AllMusicBackground", "fanart"))
            walls.append(("SkinHelper.AllMusicSongsBackground.Wall", "SkinHelper.AllMusicSongsBackground", "thumbnail"))
            walls.append(("SkinHelper.AllTvShowsBackground.Wall", "SkinHelper.AllTvShowsBackground", "fanart"))
            walls.append(("SkinHelper.AllTvShowsBackground.Poster.Wall", "SkinHelper.AllTvShowsBackground", "poster"))
            # get the wall images...
            process_method_on_list(self.update_wall_background, walls)

    def update_wall_background(self, wall_tuple):
        '''update a single wall background'''

        win_prop = wall_tuple[1]
        wall_win_prop = wall_tuple[0]
        wall_win_prop_bw = wall_win_prop + ".BW"
        wall_type = wall_tuple[2]
        wall_images = []
        if wall_win_prop in self.all_wall_images and xbmcvfs.exists(WALLS_PATH):
            # the wall images are already cached in memory
            wall_images = self.all_wall_images[wall_win_prop]
        elif win_prop in self.all_backgrounds_keys:
            # no wall images in cache, we must retrieve them
            images = self.get_images_from_path(self.all_backgrounds_keys[win_prop], 1000)
            if images:
                wall_images = self.get_wallimages(wall_win_prop, images, wall_type)
                self.all_wall_images[wall_win_prop] = wall_images
        if wall_images:
            # we have some wall images, select a random one and set as window prop
            wall_image = random.choice(wall_images)
            if wall_image:
                self.win.setProperty(wall_win_prop, wall_image["wall"])
                self.win.setProperty(wall_win_prop_bw, wall_image["wallbw"])

    def get_wallimages(self, win_prop, images, art_type="fanart"):
        '''gets or builds all wall images for the collection'''
        wall_images = []

        if self.build_busy.get(win_prop, False):
            # there is already a build in progress for this wall, skip...
            log_msg("Build WALL %s skipped - another build in progress" % win_prop)
            return wall_images
        else:
            self.build_busy[win_prop] = True

        # check if our path exists
        if not xbmcvfs.exists(WALLS_PATH):
            xbmcvfs.mkdirs(WALLS_PATH)
            xbmcvfs.mkdir(WALLS_PATH)

        # reuse the existing images - do not rebuild all the time
        files = xbmcvfs.listdir(WALLS_PATH)[1]
        for file in files:
            # return color and bw image combined - only if both are found
            color_path = WALLS_PATH + file.replace("_BW", "")
            black_path = WALLS_PATH + file
            if file.startswith("%s_BW." % win_prop) and xbmcvfs.exists(color_path):
                wall_images.append(
                    {
                        "wallbw": black_path,
                        "wall": color_path
                    })

        # skip if we do not have enough source images
        if images < self.max_wallimages * 2:
            log_msg("Building WALL background skipped - not enough source images")
            return wall_images

        # build wall images if we do not already have (enough) wall images prebuilt on the filesystem
        if self.has_pil and len(wall_images) < self.max_wallimages:
            wall_images = self.build_wallimages(win_prop, images, art_type)

        self.build_busy[win_prop] = False
        return wall_images

    def build_wallimages(self, win_prop, images, art_type):
        '''build wall images with PIL module for the collection'''
        wall_images = []
        return_images = []
        log_msg("Building Wall background for %s - this might take a while..." % win_prop)
        if art_type == "thumbnail":
            # square images
            img_columns = 11
            img_rows = 7
            img_width = 260
            img_height = 260
        elif art_type == "poster":
            # poster images
            img_columns = 15
            img_rows = 5
            img_width = 128
            img_height = 216
        else:
            # landscaped images
            img_columns = 8
            img_rows = 8
            img_width = 240
            img_height = 135
        size = img_width, img_height

        # build the wall images
        images_required = img_columns * img_rows
        for image in images:
            image = image.get(art_type, "")
            if xbmcvfs.exists(image):
                wall_images.append(image)

        if wall_images:
            # duplicate images if we don't have enough

            while len(wall_images) < images_required:
                wall_images += wall_images

            for count in range(self.max_wallimages):
                if self.exit:
                    return []
                random.shuffle(wall_images)
                img_canvas = Image.new("RGBA", (img_width * img_columns, img_height * img_rows))
                img_count = 0
                for x in range(img_rows):
                    for y in range(img_columns):
                        file = xbmcvfs.File(wall_images[img_count])
                        try:
                            img_obj = io.BytesIO(bytearray(file.readBytes()))
                            img = Image.open(img_obj)
                            img = img.resize(size)
                            img_canvas.paste(img, (y * img_width, x * img_height))
                            del img
                        except Exception:
                            log_msg("Invalid image file found! --> %s" % wall_images[img_count], xbmc.LOGWARNING)
                        finally:
                            file.close()
                            img_count += 1

                # save the files..
                out_file = "%s%s.%s.jpg" % (WALLS_PATH, win_prop, count)
                out_file = xbmc.translatePath(out_file).decode("utf-8")
                if xbmcvfs.exists(out_file):
                    xbmcvfs.delete(out_file)
                    xbmc.sleep(500)
                img_canvas.save(out_file, "JPEG")

                out_file_bw = "%s%s_BW.%s.jpg" % (WALLS_PATH, win_prop, count)
                out_file_bw = xbmc.translatePath(out_file_bw).decode("utf-8")
                if xbmcvfs.exists(out_file_bw):
                    xbmcvfs.delete(out_file_bw)
                    xbmc.sleep(500)
                img_canvas = img_canvas.convert("L")
                img_canvas.save(out_file_bw, "JPEG")
                del img_canvas
                # add our images to the dict
                return_images.append({"wall": out_file, "wallbw": out_file_bw})
        log_msg("Building Wall background %s DONE" % win_prop)
        return return_images

    def set_manualwall(self, win_prop, limit=20):
        '''set a manual wall by providing the skinner randomly changing images in window props'''
        images = self.get_images_from_path(self.all_backgrounds_keys[win_prop], 1000)
        if images:
            if self.win.getProperty("%s.Wall.0" % win_prop):
                # 1st run was already done so only refresh one random image in the collection...
                image = random.choice(images)
                for key, value in image.iteritems():
                    random_int = random.randint(0, limit)
                    if key == "fanart":
                        self.win.setProperty("%s.Wall.%s" % (win_prop, random_int), value)
                    else:
                        self.win.setProperty("%s.Wall.%s.%s" % (win_prop, random_int, key), value)
            else:
                # first run: set all images
                for i in range(limit):
                    image = random.choice(images)
                    for key, value in image.iteritems():
                        if key == "fanart":
                            self.win.setProperty("%s.Wall.%s" % (win_prop, i), value)
                        else:
                            self.win.setProperty("%s.Wall.%s.%s" % (win_prop, i, key), value)

    def update_manualwalls(self):
        '''manual wall images, provides a collection of images which are randomly changing'''
        for key, value in self.manual_walls.iteritems():
            set_manualwall(key, value)
