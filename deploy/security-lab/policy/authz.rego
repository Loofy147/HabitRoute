package envoy.authz

import rego.v1

default allow := false

# Only the two declared operations are allowed through the proxy.
allow if {
  input.attributes.request.http.method == "GET"
  input.attributes.request.http.path == "/health"
}

allow if {
  input.attributes.request.http.method == "POST"
  input.attributes.request.http.path == "/mutate"
}
