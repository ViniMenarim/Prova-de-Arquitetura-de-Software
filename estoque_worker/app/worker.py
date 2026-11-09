import json
import os
import signal
import sys
import time

import pika

FILA = "estoque.queue"
EXCHANGE = "pedido.criado.fanout"
DEAD_EXCHANGE = "pedido.dead"
DLQ = f"{FILA}.dlq"
PROCESSADOS: set[str] = set()


def conectar() -> pika.BlockingConnection:
    params = pika.URLParameters(os.environ["AMQP_URL"])
    for n in range(1, 31):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            print(f"[estoque] RabbitMQ indisponível (tentativa {n}/30)", flush=True)
            time.sleep(2)
    raise RuntimeError("RabbitMQ não respondeu a tempo")


def ao_receber(canal, metodo, propriedades, corpo: bytes) -> None:
    try:
        evento = json.loads(corpo)
        if not isinstance(evento, dict) or not all(
            chave in evento for chave in ("id", "cliente", "email", "valor_total")
        ):
            raise ValueError("campos obrigatórios ausentes")
        if not all(isinstance(evento[chave], str) for chave in ("id", "cliente", "email")):
            raise ValueError("campos de texto inválidos")
        if not isinstance(evento["valor_total"], (int, float)) or evento["valor_total"] <= 0:
            raise ValueError("campos obrigatórios ausentes")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
        print("[estoque] Mensagem inválida enviada à DLQ", flush=True)
        canal.basic_nack(metodo.delivery_tag, requeue=False)
        return
    if evento["id"] not in PROCESSADOS:
        print(f"[estoque] Reserva solicitada para o pedido {evento['id'][:8]}", flush=True)
        PROCESSADOS.add(evento["id"])
    canal.basic_ack(metodo.delivery_tag)


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    con = conectar()
    canal = con.channel()
    canal.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)
    canal.exchange_declare(exchange=DEAD_EXCHANGE, exchange_type="direct", durable=True)
    canal.queue_declare(queue=DLQ, durable=True)
    canal.queue_bind(queue=DLQ, exchange=DEAD_EXCHANGE, routing_key=FILA)
    canal.queue_declare(queue=FILA, durable=True, arguments={
        "x-dead-letter-exchange": DEAD_EXCHANGE,
        "x-dead-letter-routing-key": FILA,
    })
    canal.queue_bind(queue=FILA, exchange=EXCHANGE)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue=FILA, on_message_callback=ao_receber)
    print("[estoque] Aguardando mensagens...", flush=True)
    try:
        canal.start_consuming()
    finally:
        con.close()


if __name__ == "__main__":
    main()
