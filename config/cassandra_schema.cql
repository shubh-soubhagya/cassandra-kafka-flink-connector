CREATE KEYSPACE IF NOT EXISTS recommendation
WITH replication = {'class':'SimpleStrategy','replication_factor':1};

USE recommendation;

CREATE TABLE IF NOT EXISTS user_activity (
    user_id text,
    product_id text,
    action text,
    ts timestamp,
    PRIMARY KEY ((user_id), ts)
);

CREATE TABLE IF NOT EXISTS recommendations (
    user_id text,
    product_id text,
    score float,
    PRIMARY KEY ((user_id), product_id)
);
