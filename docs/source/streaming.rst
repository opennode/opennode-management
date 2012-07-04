Event streaming
===============

Streaming is a way for OMS clients to subscribe to changes in model state
including model attribute change, container membership changes and raw value streams
for simple models representing raw values (such as performance metrics)

Server side stream
------------------

Each model having an adaptor for the IStream interface can provide stream events to the OMS clients.

By default there is an IStream adapter for all Model classes called TransientStream, which records all model attribute
changes into a (capped) in-memory list of timestamped events which can be used by clients to keep their view of models up to date.

However, special models can have their own IStream adapters for emitting special events. This is used for example by the KNOT plugin 
in order to generate other kinds of events such as performance metrics, which aren't modeled as simple attribute value changes in order
to provide a more compact wire protocol (see wire protocol)

Streaming wire protocol
-----------------------

Currently we support a polling based http protocol suitable for ajax clients
or any other client which performs periodic requests for pending events.

A WebSocket streaming event pusher protocol is also planned but not implemented yet

HTTP wire protocol
~~~~~~~~~~~~~~~~~~

The HTTP streaming protocol is client-initiated, non blocking and stateless:

Each streaming request is initiated with a POST call to '/stream' with a JSON-encoded list of streams
to be subscribed, which we shall call "subscription array":

.. code-block:: js

  POST /stream?after= HTTP/1.1
  Content-Type: application/json
  ...

  ["/machines/dec05233-cc7c-5a8c-8919-d8454bf894ae/","/machines/3c17035c-a9b5-5660-9f3d-a41e98280ef5/", ....]


The server will return a reponse encoding all the events occurred after the given timestamp passed in the "after" parameter:

.. code-block:: js

  [
    1341427149494, 
    {
      "13": [
        [
          1341427148125, 
          {
            "old_value": 635276.79, 
            "name": "uptime", 
            "value": 635292.57, 
            "event": "change"
          }
        ]
      ]
    }
  ]


If "after" is null or omitted, all the events are returned. This happens the first time the client performs a streaming request.

The response block is composed of an array containing two elements: the server side timestamp of the response (called also "relativistic token" :-) )
and a event dictionary whose key represent numerical indices of the subscription array.

The server side timestamp is passed to the client so that the subsequent /stream POST request will use this timestamp for it's "after"
parameter. This way the client won't miss any event nor get duplicate events. It's important that the timestamp is given by the server
since the client and server clocks can drift.

For each matching subscription the server returns a list of events, order by timestamp.

The format of the single event is:

.. code-block:: javascript

        [
          1341427148125, 
          <event-specific-payoad>
        ]

Namely, a timestamp of this particular event and an event specific payload.

For example the payload for an model change even is:

.. code-block:: javascript

          {
            "old_value": 635276.79, 
            "name": "uptime", 
            "value": 635292.57, 
            "event": "change"
          }


Other kind of events, like performance metrics might have a more compact encoding that requres special handling in the clients.
This is an example of performance metrics:

.. code-block:: javascript

  [
    1341427149494, 
    {
      "13": [
        [
          1341427148125, 
          12312
        ]
      ],
      "34": [
        [
          1341427148131, 
          12312
        ]
      ]
    }
  ]



Optimizations of the HTTP wire protocol
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The response format is designed to be compact even in case of a large number of subscribed objects, because
it only consumes space for events that actually happened.

The subscription array, on the other hand, has to be always sent fully. This allows the server
to avoid maintaining per client state, allows the response format to remain simple and compact because it simply
references the position of the subscribed entity in the subscription array, and allows the client to avoid
issuing explicit subscribe/unsubscribe commands which are difficult to implement correctly in case of partial
http failures, server restarts and server failovers.

A simple optimization that maintains the stateless design, yet avoids sending the full subscription array at
every poll call, is achieved by simply passing the sha1 hash of the subscription array instead of the subscription array itself.

If the server doesn't know about the hash, then the http call fails, and the client tries again using a normal full subscription array.
The server will record the "seen" subscription arrays and their hashes in a (capped) dictionary so that next time it can process the hash.

This solution reduces the wire protocol overhead (it can be see as a protocol compression) while keeping the client simple and offers seamless
server restart, load balancing and failover support.

If the client doesn't want to compute the sha1 hash (which requires yet another library), it can exploit the fact that the server returns a custom
"X-OMS-Subscription-Hash" header.

