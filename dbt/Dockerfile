FROM python:3.12-slim

WORKDIR /dbt

COPY requirements-dbt.txt .
RUN pip install --no-cache-dir -r requirements-dbt.txt

COPY astros_dbt ./astros_dbt

WORKDIR /dbt/astros_dbt

# profiles.yml лежит внутри проекта, поэтому явно указываем DBT_PROFILES_DIR
ENV DBT_PROFILES_DIR=/dbt/astros_dbt

ENTRYPOINT ["dbt"]
CMD ["run"]
