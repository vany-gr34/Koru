# Mobile app (Expo / React Native)

Not scaffolded yet. To create it from this folder's parent:

```bash
npx create-expo-app@latest mobile --template blank-typescript
cd mobile
npx expo start        # scan the QR code with the Expo Go app on your phone
```

The app talks to the backend:

| Call | When |
|---|---|
| `POST /chat {thread_id, message}` | user submits their messy tasks |
| `POST /resume {thread_id, answer}` | user answers a question (`status: "needs_input"`) |
| `GET /week/{thread_id}` | show the current week |

On a real phone, `localhost` is the phone itself. Use your computer's LAN IP instead
(e.g. `http://192.168.1.20:8000`), and make sure both are on the same Wi-Fi.

MVP screens: brain-dump input → proposed plan (list or week grid) → approve / tweak.
