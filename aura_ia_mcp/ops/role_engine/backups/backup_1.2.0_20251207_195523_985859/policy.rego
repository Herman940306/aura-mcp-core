
package authz
default allow = false
allow {
    input.user.role == "admin"
    input.user.mfa_enabled == true
}
