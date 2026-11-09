import re

import pika
import pytest
from fastapi.testclient import TestClient

from app.main import app, obter_publicador


class PublicadorFalso:
    def __init__(self):
        self.eventos = []

    def publicar(self, evento: dict) -> None:
        self.eventos.append(evento)


class PublicadorIndisponivel:
    def publicar(self, evento: dict) -> None:
        raise pika.exceptions.AMQPConnectionError("broker fora do ar")


@pytest.fixture
def cliente():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_pedido_valido_retorna_202_e_publica_email(cliente):
    falso = PublicadorFalso()
    app.dependency_overrides[obter_publicador] = lambda: falso

    resposta = cliente.post("/pedidos", json={
        "cliente": "Ana Souza", "email": "ana@example.com", "valor_total": 300.0
    })

    assert resposta.status_code == 202
    assert resposta.json()["status"] == "RECEBIDO"
    assert re.fullmatch(r"[0-9a-f-]{36}", resposta.json()["id"])
    assert len(falso.eventos) == 1
    assert falso.eventos[0]["id"] == resposta.json()["id"]
    assert falso.eventos[0]["email"] == "ana@example.com"


def test_pedido_invalido_retorna_422_e_nao_publica(cliente):
    falso = PublicadorFalso()
    app.dependency_overrides[obter_publicador] = lambda: falso

    pedidos_invalidos = [
        {"cliente": "Ana Souza", "email": "ana@example.com", "valor_total": 0},
        {"cliente": "AB", "email": "ana@example.com", "valor_total": 300},
    ]
    for pedido in pedidos_invalidos:
        resposta = cliente.post("/pedidos", json=pedido)
        assert resposta.status_code == 422

    assert falso.eventos == []


def test_broker_indisponivel_retorna_503(cliente):
    app.dependency_overrides[obter_publicador] = PublicadorIndisponivel

    resposta = cliente.post("/pedidos", json={
        "cliente": "Ana Souza", "email": "ana@example.com", "valor_total": 300
    })

    assert resposta.status_code == 503


def test_saude_retorna_200(cliente):
    resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json()["api"] == "ok"
