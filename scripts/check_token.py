#!/usr/bin/env python
import sys
import hmac
from base64 import urlsafe_b64encode as encodestring, urlsafe_b64decode as decodestring

token = sys.argv[1]

print "DEBASE64:", repr(decodestring(token))

head, signature = decodestring(token).split(';', 1)

print "HEAD:", head
print "SIGNATURE:", repr(signature)


check_sig = hmac.new('change_me', head).digest()

print "CHECK SIG:", repr(check_sig)

print "EQUALS?", check_sig == signature
