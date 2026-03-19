# Mobile UX

The web application is primarily accessed via phone. Therefore, traditional dense wide-screen chat interfaces are inappropriate. The UX prioritizes thumb reachability and visual contrast.

## 1. General Layout
- **Bottom-Heavy Input**: The primary interaction field is locked to the bottom, avoiding layout shifts when the virtual keyboard extends. 
- **Sticky Transcript**: As the user speaks or types, the chat transcript auto-scrolls. 
- **Vapi "Talk" FAB**: A floating action button acts as a push-to-talk OR a tap-to-mute interface overriding the text bar completely across the layout. 

## 2. Action Cards
Action Cards represent the system pausing to ask for execution permissions.
- They are not pop-ups. They are inserted directly into the chat stream sequence.
- **Visual Design**: High contrast boundaries containing the targeted system (HubSpot icon), the proposed action ("Move Deal to Closed"), and the specific target name ("Acme Corp").
- Buttons must be large enough to tap safely while walking. "Approve" (Green/Primary) and "Reject" (Red/Secondary).

## 3. "Thinking" Indicators
Latency across LangGraph can range from 3s to 20s. We must continuously telegraph state to the user to prevent abandonment.
- "Evaluating request..."
- "Routing to CFO Layer..."
- "Querying invoice database..."
These messages are derived by polling the backend and observing which node currently possesses the state ball.

## 4. Voice Gracefulness
If the user is operating via Voice natively using Vapi, Vapi cannot render an Action Card. The system must announce via TTS: "I am ready to move the deal, but I need your approval in the application." The user pulls the phone out, views the streamed transcript, and taps the card.
