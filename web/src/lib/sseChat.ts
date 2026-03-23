export type ChatStreamDoneEvent = {
    type: "done";
    thread_id: string;
    active_agent?: string;
    status?: string;
    pending_approval?: boolean;
    approval_gate_id?: string | null;
};

/**
 * Consumes newline-delimited SSE `data: {...}` frames from a fetch response body.
 */
export async function consumeChatSse(
    body: ReadableStream<Uint8Array> | null,
    handlers: {
        onDelta: (text: string) => void;
        onDone: (event: ChatStreamDoneEvent) => void;
        onError: (message: string) => void;
        /** First-byte / lifecycle hints from the agent stream (before model tokens). */
        onStatus?: (text: string) => void;
    }
): Promise<void> {
    if (!body) {
        throw new Error("No response body");
    }
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let carry = "";
    let sawDone = false;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        carry += decoder.decode(value, { stream: true });

        let sep: number;
        while ((sep = carry.indexOf("\n\n")) !== -1) {
            const block = carry.slice(0, sep);
            carry = carry.slice(sep + 2);
            const line = block.trim();
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6);
            let data: Record<string, unknown>;
            try {
                data = JSON.parse(raw) as Record<string, unknown>;
            } catch {
                handlers.onError(`Invalid SSE JSON: ${raw.slice(0, 200)}`);
                continue;
            }
            const t = data.type;
            if (t === "delta" && typeof data.text === "string") {
                handlers.onDelta(data.text);
            } else if (t === "status" && typeof data.text === "string") {
                handlers.onStatus?.(data.text);
            } else if (t === "done") {
                sawDone = true;
                handlers.onDone(data as ChatStreamDoneEvent);
            } else if (t === "error" && typeof data.message === "string") {
                handlers.onError(data.message);
            }
        }
    }
    if (!sawDone) {
        handlers.onError("Stream closed before completion (no done frame). Check backend logs and network.");
    }
}
