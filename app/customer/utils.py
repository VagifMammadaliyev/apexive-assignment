import string
import random


# This method is not used anymore, we generate client code from phone number.
# This method is keeped because it is used in a migration file to populate null client codes
generate_client_code = lambda l: "".join(random.choice(string.digits) for _ in range(l))
