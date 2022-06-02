import harvesters.core as harvester

def main():
    h = harvester.Harvester()
    h.add_file("C:\\Users\\Paavo\\Documents\\ADENN2021\\MATRIX VISION\\bin\\x64\\mvGenTLProducer.cti")
    testi = int("Size1440"[4:])
    print(testi)
    print("Size"+str(testi))

    h.update()
    if len(h.device_info_list) > 0:
        cam = h.create_image_acquirer(0)
        camprops = cam.remote_device.node_map
        print(dir(camprops))
        print(camprops.get_node("GevTimestampTickFrequency").value)
        #print(dir(camprops.LoadParameters))
        #print(dir(camprops.get_node("PacketSize")))

        #camprops.get_node("UserSetSelector").value = "UserSet1"
        #print(dir(camprops.get_node("ExposureTimeAbs")))
        #camprops.get_node("UserSetSave").execute()
        cam.destroy()
    h.reset()
main()