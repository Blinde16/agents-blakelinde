import { ChatStream } from "@/components/chat/ChatStream";
import { Controls } from "@/components/chat/Controls";

export default function Home() {
    return (
        <div className="flex flex-col h-full w-full relative">
            {/* The primary conversation stream */}
            <ChatStream />
            
            {/* Bottom-anchored control bar */}
            <Controls />
        </div>
    );
}
