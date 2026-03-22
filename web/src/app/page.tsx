import { ChatStream } from "@/components/chat/ChatStream";
import { Controls } from "@/components/chat/Controls";
import { Sidebar } from "@/components/chat/Sidebar";

export default function Home() {
    return (
        <div className="flex h-full w-full relative">
            {/* Context Sidebar */}
            <Sidebar />
            
            <div className="flex flex-col flex-1 relative h-full">
                {/* The primary conversation stream */}
                <ChatStream />
                
                {/* Bottom-anchored control bar */}
                <Controls />
            </div>
        </div>
    );
}
