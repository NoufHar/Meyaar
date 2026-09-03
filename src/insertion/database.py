from sqlalchemy import create_engine, text


def create_db_engine():

    username = "postgres"
    password = ""
    host = "localhost"
    port = "5432"
    database = "meyaar_db"

    database_url = (
        f"postgresql+psycopg2://{username}:{password}"
        f"@{host}:{port}/{database}"
    )

    engine = create_engine(database_url)

    return engine


def connect_to_db(engine):

    with engine.connect() as connection:

        result = connection.execute(
            text("SELECT PostGIS_Version();")
        )

        version = result.scalar()

        return {
            "status": "connected",
            "postgis_version": version
        }