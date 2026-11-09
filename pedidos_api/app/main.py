import json
import os
import uuid
from datetime import datetime, timezone

import pika
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

EXCHANGE = "pedido.criado.fanout"
DEAD_EXCHANGE = "pedido.dead"
FILAS = ("notificacoes.queue", "estoque.queue")


class PedidoEntrada(BaseModel):
    cliente: str = Field(min_length=3, max_length=120)
    email: str
    valor_total: float = Field(gt=0)


class PedidoRecebido(BaseModel):
    id: str
    status: str


class PublicadorRabbit:
    def __init__(self, url: str):
        self.params = pika.URLParameters(url)

    def publicar(self, evento: dict) -> None:
        with pika.BlockingConnection(self.params) as con:
            canal = con.channel()
            canal.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)
            canal.exchange_declare(exchange=DEAD_EXCHANGE, exchange_type="direct", durable=True)
            for fila in FILAS:
                canal.queue_declare(queue=f"{fila}.dlq", durable=True)
                canal.queue_bind(queue=f"{fila}.dlq", exchange=DEAD_EXCHANGE, routing_key=fila)
                canal.queue_declare(queue=fila, durable=True, arguments={
                    "x-dead-letter-exchange": DEAD_EXCHANGE,
                    "x-dead-letter-routing-key": fila,
                })
                canal.queue_bind(queue=fila, exchange=EXCHANGE)
            canal.basic_publish(
                exchange=EXCHANGE,
                routing_key="",
                body=json.dumps(evento).encode(),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=pika.DeliveryMode.Persistent,
                    message_id=evento["id"],
                ),
            )


def obter_publicador() -> PublicadorRabbit:
    return PublicadorRabbit(os.environ.get("AMQP_URL", "amqp://app:troque-mq@localhost:5672/"))


app = FastAPI(title="Pedidos API", version="1.1.0")


@app.get("/saude")
def saude():
    return {"api": "ok"}


@app.post("/pedidos", response_model=PedidoRecebido, status_code=status.HTTP_202_ACCEPTED)
def criar_pedido(entrada: PedidoEntrada, publicador: PublicadorRabbit = Depends(obter_publicador)):
    evento = {
        "id": str(uuid.uuid4()),
        "cliente": entrada.cliente,
        "email": str(entrada.email),
        "valor_total": entrada.valor_total,
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }
    try:
        publicador.publicar(evento)
    except pika.exceptions.AMQPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Broker de mensagens indisponível") from exc
    return {"id": evento["id"], "status": "RECEBIDO"}
