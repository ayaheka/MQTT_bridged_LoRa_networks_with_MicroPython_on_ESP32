# coding: utf-8

import worker_upython
import config_lora
import payload
import packet
import router


class Gateway(worker_upython.Worker, config_lora.Controller, router.Router):
    
    def __init__(self, server_address, server_port,
                 pin_id_led = config_lora.Controller.ON_BOARD_LED_PIN_NO, 
                 on_board_led_high_is_on = config_lora.Controller.ON_BOARD_LED_HIGH_IS_ON,
                 pin_id_reset = config_lora.Controller.PIN_ID_FOR_LORA_RESET,
                 blink_on_start = (2, 0.5, 0.5)):
                 
        self.eui = config_lora.NODE_EUI
        config_lora.Controller.__init__(self, 
                                        pin_id_led,
                                        on_board_led_high_is_on,
                                        pin_id_reset,
                                        blink_on_start)
        router.Router.__init__(self)
        worker_upython.Worker.__init__(self, server_address, server_port)        
        self.name = config_lora.NODE_EUI  # use NODE_EUI as MQTT name
        self.set_connection_name = lambda : None 
        

    def received_packet(self, payload_string, rssi = None):
        pay_load = payload.Payload().loads(payload_string)
        pkt = packet.Packet(self.eui, rssi, pay_load, pay_load.time)
        return pkt

        
    def received_packet_update_link(self, transceiver, payload_bytes):
        self.blink_led()   
                
        try:
            payload_string = payload_bytes.decode()
            rssi = transceiver.packetRssi()
            print("*** Received message ***\n{}".format(payload_string))
            
            pkt = self.received_packet(payload_string, rssi)
            if config_lora.IS_TTGO_LORA_OLED: transceiver.show_packet(payload_string, rssi)  
            
            if not self.is_a_gateway(pkt.pay_load.frm):
                self.update_link_from_packet(pkt)
                if self.is_nearest_gateway(pkt.pay_load.frm):
                    self.ack(pkt.pay_load)
                    self.dispatch_payload(pkt.pay_load) 
                    self.publish_received_payload(pkt.pay_load)
            
        except Exception as e:
            print(e) 
            
        
    def ack(self, pay_load):
        self.send_payload(pay_load.gen_ack_payload(self.eui))
        

    def _get_transceiver(self, name = 'LoRa'):
        return self.transceivers.get(name)
        
        
    def send_payload(self, pay_load, return_to_rx_mode = True):
        self.transmit_payload(pay_load.dumps(), return_to_rx_mode) 
        
        
    def transmit_payload(self, payload_string, return_to_rx_mode = True):
        pay_load = payload.Payload().loads(payload_string)
        pay_load.via = self.eui
        transceiver = self._get_transceiver()
        transceiver.println(pay_load.dumps())
        if return_to_rx_mode: transceiver.receive()
        
        
    def dispatch_payload(self, pay_load, broadcast = False):        
        if broadcast or pay_load.to is None:    # destination not specified.
            receiver = 'Hub'
        elif self.is_a_gateway(pay_load.to):    # is a gateway 
            receiver = pay_load.to
        else:
            receiver = self.get_nearest_gateway_eui(pay_load.to)        
            if not receiver:                    # Unknown. something else, not a gateway or node.
                return 
        
        message = {'receiver': receiver,
                   'message_type': 'function',
                   'function': 'transmit_payload',
                   'kwargs': {'payload_string': pay_load.dumps()}}
        self.request(message)


    def dispatch_payload_json(self, pay_load_json, broadcast = False):
        pl = payload.Payload().loads(pay_load_json)
        self.dispatch_payload(pl, broadcast)
        

    def broadcast_payload(self, pay_load):
        self.dispatch_payload(pay_load, broadcast = True)
        
        
    def publish_received_payload(self, pay_load, prefix = 'received'):
        receiver = '/'.join([prefix, pay_load.frm])
        
        message = {'receiver': receiver,
                   'message_type': 'function',
                   'function': 'process_payload',
                   'kwargs': {'pay_load_json': pay_load.dumps()}}
        self.request(message) 
        

    def process_payload(self, pay_load_json):
        # pay_load = payload.Payload().loads(pay_load_json)
        pass
        

        
Worker = Gateway
