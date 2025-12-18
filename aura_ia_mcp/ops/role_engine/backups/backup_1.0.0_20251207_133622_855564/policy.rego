
package authz
default allow = false
allow { input.user.role == "admin" }
