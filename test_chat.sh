#!/bin/bash
curl -X POST http://localhost:9201/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message":"System check","mode":"concierge","conversation_id":"check"}'
