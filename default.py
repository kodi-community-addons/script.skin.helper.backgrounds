#!/usr/bin/python
# -*- coding: utf-8 -*-

'''If called as script provides a dialog to configure conditional backgrounds '''
from resources.lib.conditional_backgrounds import ConditionalBackgrounds
window = ConditionalBackgrounds("DialogSelect.xml", "")
window.doModal()
del window
