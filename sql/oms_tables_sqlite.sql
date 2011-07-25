
CREATE TABLE compute
(
  id INTEGER PRIMARY KEY,
  architecture VARCHAR,
  hostname VARCHAR,
  speed REAL,
  memory REAL,
  state VARCHAR,
  template_id INTEGER,
  FOREIGN KEY (template_id) REFERENCES template(id)
);

CREATE TABLE storage
(
  id INTEGER PRIMARY KEY,
  size REAL,
  state VARCHAR
);

CREATE TABLE tag
(
  id INTEGER PRIMARY KEY,
  name VARCHAR
);

CREATE TABLE network
(
  id INTEGER PRIMARY KEY,
  vlan VARCHAR,
  label VARCHAR,
  state VARCHAR,
  ipv4_address_range VARCHAR,
  ipv4_gateway VARCHAR,
  ipv6_address_range VARCHAR,
  ipv6_gateway VARCHAR,
  allocation VARCHAR
);

CREATE TABLE network_device
(
  id INTEGER PRIMARY KEY,
  network_id INTEGER,
  compute_id INTEGER,
  interface VARCHAR,
  mac VARCHAR,
  state VARCHAR,
  FOREIGN KEY (network_id) REFERENCES network(id),
  FOREIGN KEY (compute_id) REFERENCES compute(id)
);

CREATE TABLE template
(
  id INTEGER PRIMARY KEY,
  name VARCHAR,
  base_type VARCHAR,
  min_cores INTEGER,
  max_cores INTEGER,
  min_memory INTEGER,
  max_memory INTEGER
);
