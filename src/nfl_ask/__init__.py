"""The Ask page: a question goes in, an answer from the served marts comes out.

Separate from nfl_dagster on purpose: the website never imports the pipeline. It reads only
the serving database (Prisma Postgres), through query.run_query().
"""
