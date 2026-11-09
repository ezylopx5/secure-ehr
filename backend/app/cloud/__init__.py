"""UNTRUSTED CLOUD INFERENCE BOUNDARY.

Modules in this package may import ONLY tenseal/numpy and serialized model
artifacts. They have NO access to the database, the master key, the CKKS
secret key or any plaintext patient feature. This package is what you would
lift into a real cloud deployment (docker-compose service ``inference``):
everything it needs arrives as serialized ciphertexts + public context.
"""
