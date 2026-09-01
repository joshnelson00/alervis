from gql import GraphQLRequest, gql, Client, transport
from gql.transport.requests import RequestsHTTPTransport
from loguru import logger

query_url = ""

transport = RequestsHTTPTransport(
    url=query_url,
    headers={
        "Authorization": "Bearer <auth-jwt>",
        "Contexttoken": "Bearer <context-jwt>",
        "Gql-Operation-Name": "GetAllClasses",
    },
)

client = Client(
    transport=transport,
    fetch_schema_from_transport=True,
)

query = gql(
"""

"""
)

def get_classes(query: GraphQLRequest):
    classes = []
    try:
        result = client.execute(query)
        classes = result.get("getAllClass")
    except Exception as e:
        logger.error(f"An error occured: {e}")

    return classes

