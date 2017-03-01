"""Handle serial interface"""
__authors__ = "Colden Rouleau, James Paul Mason"
__contact__ = "jmason86@gmail.com"

import sys
import time
import serial

class connect_serial_decode_kiss():
    def __init__(self, port, baudRate, log):
        self.port = port
        self.baudRate = baudRate
        self.log = log
        self.log.info("Opening port: {0}".format(port))
        self.ser = serial.Serial(port, baudRate, timeout=.01)
        self.ser.flushInput()

        if (not self.ser.readable()):
            raise Exception("Port not readable")

        if (not self.ser.writable()):
            raise Exception("Port not writable")

        #class vars
        self.serial_read_storage = []

    def close(self):
        self.log.info("Closing ground station link")
        self.ser.close

    def read(self):
        data = []
        newdata = []
        while(1):
            newdata = self.ser.read(self.ser.in_waiting)
            for byte in newdata:
                data.append(byte) # JPM: This results in a list rather than a bytearray, which breaks my code. Why do this? Else how to convert to bytearray

            if(self.ser.in_waiting == 0):
                break
        return data

    #Take an arbitrary numeric data array and figure out if it is not a KISS packet, a partial KISS packet, or a full KISS packet
    #returns a control value and the packet (is_ready,[packet],[remaining_data])
    #is_ready=0 means a partial or empty packet (and returns the packet unmodified)
    #is_ready=-1 means an error occurred and the data should be tossed (returns an empty array)
    #is_ready=1 means the packet is ready
    def KISS_read(self,data):
        FRAME_END = 0xC0
        FRAME_ESC = 0xDB
        DATA_FRAME_CODE = 0x00
        TRANSPOSE_FRAME_END = 0xDC
        TRANSPOSE_FRAME_ESC = 0xDD
        FRAME_END_DATA = [FRAME_ESC,TRANSPOSE_FRAME_END]
        FRAME_ESC_DATA = [FRAME_ESC,TRANSPOSE_FRAME_ESC]
        #deal with any frame ends or frame escapes in the data
        i=0

        error = 0

        #can get fed an empty array and that's OK - just return an empty array, and "remaining_data" is all the data
        if(len(data) == 0):
            return [0,[],data]

        if(data[0] != FRAME_END):
            self.log.error("KISS_read received a packet that did not start with a FRAME_END byte (0xC0)! Please toss data!")
            error = 1

        #if we have a FRAME_END byte but nothing else, just return and wait for more data
        if(error==0 and len(data)<2):
            return [0,[],data]


        if(error==0 and data[1] != DATA_FRAME_CODE):
            self.log.error("KISS_read received a packet with where the 2nd byte was not DATA_FRAME_CODE (0x00). Cannot process, please toss data.")
            error = 1

        i = 2
        pkt_ind = 0
        packet = []
        while(error==0):
            #if don't have enough data to process, return
            if(len(data) <= i):
                return [0,[],data]
            if(data[i] == FRAME_ESC):
                i += 1 #the escaped char takes two
                #make sure we still have something to look at
                if(len(data)>i):
                    if(data[i] == TRANSPOSE_FRAME_ESC):
                        packet.append(FRAME_ESC)
                    elif(data[i] == TRANSPOSE_FRAME_END):
                        packet.append(FRAME_END)
                    else:
                        self.log.error("KISS_read saw FRAME_ESC that was not followed by either TRANSPOSE. Toss packet! (see packet printout)")
                        error = 1
                        break;
                else:
                    #we have a partial packet (since it ends with FRAME_ESC) - which is fine, we'll come back later
                    return(0,[],data)

            #check to see if we're done
            elif(data[i] == FRAME_END):
                #make sure we don't have an empty packet
                if(len(packet)>0):
                    #if we're good, return the packet and the unprocessed data
                    return(1, packet, data[i+1:])
                else:
                    self.log.error("Received an empty packet! Consisted only of KISS control bytes!")
                    error = 1
                    break;
            else:
                packet.append(data[i])

            i += 1

        if(error):
            self.log.error("KISS_read: Bytes: ")
            for byte in data:
                self.log.error(byte)
            return [-1,[],[]]
        else:
            self.log.error("CODE ERROR in KISS_read! While Loop finished without an error, and did not return!")
            return [-1,[],[]]

    def hydra_fletcher16(self,packet):
        cka = 0
        ckb = 0
        for byte in packet:
            #log.debug(byte)
            cka += byte
            cka %= 255
            ckb += cka
            ckb %= 255
        #log.debug(cka)
        #log.debug(ckb)
        return [ckb,cka]

    def ax25_crc(self,packet):
        shift_reg = 0xFFFF;
        Gen = 0x1021;
        #Gen = 0x8011;
        output_xor_mask = 0x0000;
        #output_xor_mask = 0xFFFF;
        packet = packet + [0,0]
        j = 0
        for byte in packet:
            j += 1
            #for i in range(8):
            for i in reversed(range(8)):
                inbit = (byte >> i) & 0x01
                outbit = (shift_reg & 0x8000) >> 15
                shift_reg = (shift_reg << 1) & 0xFFFF
                shift_reg += inbit
                #print("byte={0}, i={1}, inbit={2}, outbit={3}".format(hex(byte), i, inbit,outbit))
                #if( (inbit^outbit) == 1):
                if( outbit == 1):
                    shift_reg = shift_reg ^ Gen
                #print("binary CRC",bin(shift_reg))


            FCS = shift_reg ^ output_xor_mask
            print("ax25_crc: At byte {0}, crc={1}".format(j-1,hex(FCS)))
            #if(FCS == 0x7C10)

        return FCS

    def reference_test_crc(self):
        ref_string = '123456789'
        ref_array = []
        for char in ref_string:
            ref_array.append(ord(char))
        crc_ref = self.ax25_crc(ref_array)
        print("CRC ref 123456789",hex(crc_ref))

        print("")
        print("")
        print("")

        ref_string = 'A'
        ref_array = []
        for char in ref_string:
            ref_array.append(ord(char))
        crc_ref = self.ax25_crc(ref_array)
        print("CRC ref A",hex(crc_ref))

    def testRead(self):
        self.log.info("Testing read on port: {0}".format(self.port))
        portReadable = self.ser.readable()

        if portReadable:
            self.log.info("Test read on port was successful")
        else:
            self.log.error("Test read on port failed")
        return portReadable

def testReadMain(port, baudRate, log):
    log.info("Opening port: {0}".format(port))
    ser = serial.Serial(port, baudRate)

    if (not ser.readable()):
        raise Exception("Port not readable")

    #ser.flushInput()

    log.info("Finished checking serial line readability, closing: {0}".format(port))
    ser.close


if __name__ == '__main__':
    if (len(sys.argv) < 4):
        raise Exception("Must pass in port name (string), baud rate (integer), and python log reference")
    else:
        testReadMain(sys.argv[1], sys.argv[2], sys.argv[3])

