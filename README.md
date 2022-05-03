# GenICamHandler
Image acquisition software for GenICam compliant devices on 64-bit Windows.

Tested with Sony XCG-5005E GigE Vision camera.

## Requires
Python 3.7

mvImpact Acquire 2.45 http://static.matrix-vision.com/mvIMPACT_Acquire/2.45.0/

### Python Packages
    PyQT5: pip install pyqt5
  
    GenICam harvester (v1.2 recomended): pip install harvesters==1.2
  
    OpenCV: pip install opencv-python
  
Note! Other versions of the required parts might work, but have not been tested.

## Running
Change the target cti file path in camHandler.py line 27 to match your mvImpact Acquire installation path

Excecute run.py
