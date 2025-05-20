import random
import time
import json
from idlelib.debugger_r import dicttable

from fontTools.cffLib import topDictOperators2
from paho.mqtt import client as mqtt_client

broker = '192.168.45.190'
port = 1883
topico_core_0_sender = "core_0_sender"
topico_core_1_sender = "core_1_sender"
topico_core_seleccionado = "core_seleccionado"
cliente_id = f'python-mqtt-{random.randint(0, 1000)}'

direccion_seleccionada = 0
dict_Abajo_Arriba = None
dict_Derecha_Izquierda = None

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Conectado al broker MQTT!")
        else:
            print(f"Fallo en la conexión. Código de retorno: {rc}")

    client = mqtt_client.Client(cliente_id)
    client.connect(broker, port)
    return client

def manejar_mensajes(client):
    def on_message(client, userdata, msg):
        global dict_Abajo_Arriba, dict_Derecha_Izquierda, direccion_seleccionada
        cantidadCoches_AA = 0;
        cantidadCoches_DI = 0;
        contadorTrafico_AA = 0;
        contadorTrafico_DI = 0;
        contadorPulsadores_AA = 0;
        contadorPulsadores_DI = 0;

        if msg.topic == topico_core_0_sender:
            data = json.loads(msg.payload.decode())
            dict_Abajo_Arriba = data
            #print(f"Mensaje recibido de Core 0: {data}")
            #print(data["primera_cola"])
        elif msg.topic == topico_core_1_sender:
            data = json.loads(msg.payload.decode())
            dict_Derecha_Izquierda = data
            #print(f"Mensaje recibido de Core 1: {data}")
            #print(data["segunda_cola"])
        if dict_Derecha_Izquierda and dict_Abajo_Arriba:
            cantidadCoches_AA = dict_Abajo_Arriba["primera_cola"] + dict_Abajo_Arriba["segunda_cola"]
            cantidadCoches_DI = dict_Derecha_Izquierda["primera_cola"] + dict_Derecha_Izquierda["segunda_cola"]
            contadorPulsadores_AA = dict_Abajo_Arriba["primer_boton"] + dict_Abajo_Arriba["segundo_boton"]
            contadorPulsadores_DI = dict_Derecha_Izquierda["primer_boton"] + dict_Derecha_Izquierda["segundo_boton"]

            if dict_Abajo_Arriba["primera_cola"] > 11:
                contadorTrafico_AA += 1
            if dict_Abajo_Arriba["segunda_cola"] > 11:
                contadorTrafico_AA += 1
            if dict_Derecha_Izquierda["primera_cola"] > 11:
                contadorTrafico_DI += 1
            if dict_Derecha_Izquierda["segunda_cola"] > 11:
                contadorTrafico_DI += 1

            print("Botones Arriba abajo:", contadorPulsadores_AA," Botones Derecha izquierda:", contadorPulsadores_DI)
            print("Trafico Arriba abajo:", contadorTrafico_AA, "Trafico Derecha izquierda:", contadorTrafico_DI)

            if contadorTrafico_AA > contadorTrafico_DI:
                direccion_seleccionada = 0
            elif contadorTrafico_AA == contadorTrafico_DI > 0 and cantidadCoches_AA > cantidadCoches_DI:
                direccion_seleccionada = 0
            elif contadorTrafico_AA == contadorTrafico_DI > 0 and cantidadCoches_AA == cantidadCoches_DI and contadorPulsadores_AA < contadorPulsadores_DI:
                direccion_seleccionada = 0
            elif contadorTrafico_AA == contadorTrafico_DI == 0 and contadorPulsadores_AA < contadorPulsadores_DI:
                direccion_seleccionada = 0

            if contadorTrafico_AA < contadorTrafico_DI:
                direccion_seleccionada = 1
            elif contadorTrafico_AA == contadorTrafico_DI > 0 and cantidadCoches_AA < cantidadCoches_DI:
                direccion_seleccionada = 1
            elif contadorTrafico_AA == contadorTrafico_DI > 0 and cantidadCoches_AA == cantidadCoches_DI and contadorPulsadores_AA > contadorPulsadores_DI:
                direccion_seleccionada = 1
            elif contadorTrafico_AA == contadorTrafico_DI == 0 and contadorPulsadores_AA > contadorPulsadores_DI:
                direccion_seleccionada = 1





    client.subscribe([(topico_core_0_sender, 0), (topico_core_1_sender, 0)])
    client.on_message = on_message

def publicar_seleccion(client):
    global direccion_seleccionada
    while True:
        mensaje = {
            "coreSeleccionado": direccion_seleccionada
        }
        client.publish(topico_core_seleccionado, json.dumps(mensaje))
        print(f"Publicado en {topico_core_seleccionado}: {mensaje}")
        direccion_seleccionada = 1 - direccion_seleccionada
        time.sleep(6)

def run():
    client = connect_mqtt()
    manejar_mensajes(client)

    import threading
    hilo_publicacion = threading.Thread(target=publicar_seleccion, args=(client,))
    hilo_publicacion.daemon = True
    hilo_publicacion.start()

    print("Esperando mensajes de Core 0 y Core 1...")
    client.loop_forever()

if __name__ == '__main__':
    run()