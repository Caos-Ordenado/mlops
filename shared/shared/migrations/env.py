import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Correctly add the project root to sys.path to find the 'shared' module
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# Import Base from your models
from shared.models.base import Base # Assuming Base is in shared.models.base

# Explicitly import all model files to ensure they are registered with Base.metadata
from shared.models import webpage # This line ensures webpage.py is executed and WebPage model is registered
# Add other model imports here if you have them, e.g.:
# from shared.models import user_model
# from shared.models import product_model

# If your models are directly in shared.models, adjust as needed (e.g., from shared import models)
# Also ensure all your model files are imported somewhere so Base knows about them.
# This might require importing specific model files if they aren't automatically loaded
# e.g., from shared.models import webpage # if webpage.py contains WebPage model

# Print all tables known to Base.metadata for debugging
print("Tables known to Base.metadata before setting target_metadata:")
for table_name, table_obj in Base.metadata.tables.items():
    print(f"  - {table_name}: {table_obj}")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line reads the ini file and sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the metadata for autogenerate support
# target_metadata = None # Original line
target_metadata = Base.metadata # Use your project's Base metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:                                                                                    
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_db_connection_string():
    """Gets the database connection string from the environment variable."""
    db_url = os.getenv("DB_CONNECTION_STRING")
    print(f"[DEBUG env.py] DB_CONNECTION_STRING from os.getenv: {db_url}") # DEBUG PRINT
    if not db_url:
        # Fallback or error if not set - for alembic.ini, it can also use its own substitution
        # but for direct runs of env.py or for clarity, we can check here.
        # However, alembic.ini's %(DB_CONNECTION_STRING)s should pick it up if set in shell.
        # If running alembic commands, ensure DB_CONNECTION_STRING is exported in your shell.
        # For safety, let's try to get it from alembic.ini config if env var is not set directly in python's env
        try:
            db_url = config.get_main_option("sqlalchemy.url")
            print(f"[DEBUG env.py] sqlalchemy.url from config.get_main_option: {db_url}") # DEBUG PRINT
        except Exception:
            raise ValueError("DB_CONNECTION_STRING environment variable not set, and sqlalchemy.url not found in alembic.ini")
    print(f"[DEBUG env.py] Returning DB URL: {db_url}") # DEBUG PRINT
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    herecarbonate well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_db_connection_string()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get the Alembic configuration section (usually [alembic])
    # Ensure we have a dictionary to work with.
    db_config = config.get_section(config.config_ini_section, {})
    
    current_sqlalchemy_url = get_db_connection_string()
    print(f"[DEBUG env.py] run_migrations_online - Using sqlalchemy.url: {current_sqlalchemy_url}") # DEBUG PRINT
    db_config["sqlalchemy.url"] = current_sqlalchemy_url
    
    connectable = engine_from_config(
        db_config,  # Use the modified dictionary
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 