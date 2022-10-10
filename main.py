# rekordbox-track-id for OBS
# by: rydohg
# This project reads the track info from rekordbox using computer vision assuming
# that rekordbox is using the default theme and the 2 deck horizontal layout in 
# performance mode.

# It writes this info into text files that can be easily read by OBS Studio
# these files should be located in the rekordbox-track-id folder located 
# in same folder as the executable 

import re
import os
import time
from ctypes import windll
import win32ui
import win32gui
from PIL import Image
import numpy as np
import cv2
import pytesseract

num_screenshots = 4
dir_name = 'rekordbox-track-id/'
master_deck = -1

class TrackInfo:
  def __init__(self, name, artist, bpm, key):
    self.name = name
    self.artist = artist
    self.bpm = bpm
    self.key = key

def get_screenshots():
    window_handle = win32gui.FindWindow(None, 'rekordbox')
    
    if window_handle == 0:
        print("rekordbox not found. Make sure it's open and try again!")
        time.sleep(5)
        exit(1)
    
    left, top, right, bot = win32gui.GetWindowRect(window_handle)
    w = right - left
    h = round(235, ndigits=None)

    # Get "device contexts" to grab the recordbox window
    handleDC = win32gui.GetWindowDC(window_handle)
    mfcDC  = win32ui.CreateDCFromHandle(handleDC)
    saveDC = mfcDC.CreateCompatibleDC()

    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)

    # Take multiple screenshots because rekordbox uses Unity for the waveform/tracks
    # meaning we have to catch a full frame that shows all of this information
    # by grabbing multiple screenshots, we can consistently get 1 that has the info
    for i in range(num_screenshots):
        result = windll.user32.PrintWindow(window_handle, saveDC.GetSafeHdc(), 3)
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)

        im = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1)
        if result == 1:
            im.save(dir_name + "debugFrame" +  str(i) + ".png")
    
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(window_handle, handleDC)

def get_master_deck(raw_image):
    # Which side has the most of this specific orange? The master deck has an orange MASTER text
    global master_deck
    middle_x = round(len(raw_image[0]) / 2)
    master_deck_orange = [240, 131, 23]
    deck_1_master = len(np.where(master_deck_orange == raw_image[:, (middle_x - 150):middle_x])[0])
    deck_2_master = len(np.where(master_deck_orange == raw_image[:, len(raw_image[0]) - 150:])[0])

    if deck_1_master > deck_2_master:
        master_deck = 0
    elif deck_1_master < deck_2_master:
        master_deck = 1
    else:
        master_deck = -1

    print("Master Deck: " + str(master_deck))

def preprocess_image(raw_image):
    sharpening_kernel = np.array(
        [[0, -1, 0],
        [-1, 7,-1],
        [0, -1, 0]]
    )
    middle_x = round(len(raw_image[0]) / 2)

    # Image preprocessing pipeline, this is the most important part to the accuracy
    # I've been experimenting a lot with this so some of this code might get enabled/disabled sometimes
    # Grayscale the image, sharpen it, erode pixel(s) away, draw rectangles over unecesary info to remove unwanted text
    img = cv2.cvtColor(raw_image, cv2.COLOR_BGR2GRAY)
    img = cv2.filter2D(src=img, ddepth=-1, kernel=sharpening_kernel)
    erosion_kernel = np.ones((1,1),np.uint8)
    img = cv2.erode(img, erosion_kernel, iterations = 1)
    img = cv2.rectangle(img, (0,0), (58, len(img)), (0, 0, 0), -1)
    img = cv2.rectangle(img, (middle_x - 125, 0), (middle_x + 50, len(img)), (0, 0, 0), -1)
    img = cv2.rectangle(img, (len(img[0]) - 130, 0), (len(img[0]) - 1, len(img)), (0, 0, 0), -1)
    img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    cv2.imwrite(dir_name + 'debugProcessedImage.png', img)

    # Finally return the preprocessed halves (along the x axis) of the image
    return np.split(img, 2, 1)

def get_valid_screenshot():
    for i in range(num_screenshots):
        raw_image = cv2.imread(dir_name + "debugFrame" + str(i) + ".png")
        image_data = np.array(raw_image)
        image_variance = np.var(image_data)
        print("Variance: " + str(image_variance))

        # Blank frames don't vary in color much so I exploit that by checking its  
        # statistical variance to see if we actually have a frame with the track info
        if image_variance > 200:
            # Cut off the top 80% off the left over image (cuts off waveform)
            track_id_start_height_percentage = round(.8 * len(raw_image))
            return raw_image[track_id_start_height_percentage : len(raw_image) - 1]

def predict_text(image_data):
    deck_info = pytesseract.image_to_string(image_data).rstrip()
    print("Predicted Text:\n" + deck_info)
    track_name = deck_info.split("\n")[0]

    # Track name and artist name should be on separate lines, if not its probably a bad image
    if len(deck_info.split('\n')) < 2:
        return
    
    # Search for the BPM which is, if the OCR is right, always in that regex pattern
    # Use the BPM to know where the artist name ends
    second_line = deck_info.split('\n')[1]
    pattern = re.compile(r"[0-9]*\.[0-9]+", re.IGNORECASE)
    result = re.search(pattern, second_line)
    artist_name = second_line[0:result.start()]

    bpm = result.group()

    # After the BPM is the key, this assumes you have the Camelot system enabled
    key = second_line[result.end():].split()[0]
    key = ''.join(e for e in key if e.isalnum())
    if key[-1] == '4':
        key = key[:-1] + 'A'

    # It is possible to get the time played and time left but I didn't bother

    print("Track ID: " + track_name + ", Artist: " + artist_name + " BPM: " + bpm + " Key: " + key)
    return TrackInfo(track_name, artist_name, bpm, key)

def write_info_file(prefix, name, data):
    with open(dir_name + prefix + "_" + name + ".txt", 'w') as f:
        f.write(data)

def write_track_info_files(data, prefix):
    write_info_file(prefix, 'trackid', data.name)
    write_info_file(prefix, 'artist', data.artist)
    write_info_file(prefix, 'bpm', data.bpm)
    write_info_file(prefix, 'key', data.key)

try: 
    os.mkdir(dir_name, 0o666)
except FileExistsError as err:
    pass

print("rekordbox-track-id for OBS")
print("by: rydohg")
print("Refreshes track IDs and master deck every 15 seconds. Your rekordbox might \"blink\" when this happens")
print("This needs to be running to keep IDs up to date. Please let me know of any bugs!\n")

time.sleep(3)

while True:
    get_screenshots()
    valid_image = get_valid_screenshot()
    get_master_deck(valid_image)
    deck_images = preprocess_image(valid_image)

    if deck_images is not None and len(deck_images) > 0:
        tracks = [predict_text(deck_images[0]),  predict_text(deck_images[1])]
        for i, track in enumerate(tracks):
            if track is None:
                continue
            write_track_info_files(track, "deck_" + str(i + 1))

        if master_deck >= 0 and tracks[master_deck] is not None:
            write_track_info_files(tracks[master_deck], "master")
        else:
            print("Couldn't find master deck")

    time.sleep(15)