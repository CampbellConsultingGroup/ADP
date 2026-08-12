// ADP-914.8: ChatPanel's new getDiagramContext/onAssistantReply/
// onStreamingChange props (added incrementally across US1/US2).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPanel from "./ChatPanel";
import * as chatApi from "../api/chat";

vi.mock("../api/chat");

const mockedChatApi = vi.mocked(chatApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedChatApi.useCreateConversation.mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue({ id: "conv-1", title: "New", created_at: "", updated_at: "" }),
  } as unknown as ReturnType<typeof chatApi.useCreateConversation>);
  mockedChatApi.useConversation.mockReturnValue({
    data: { id: "conv-1", title: "New", created_at: "", updated_at: "", messages: [] },
  } as unknown as ReturnType<typeof chatApi.useConversation>);
  mockedChatApi.useConversations.mockReturnValue({ data: [] } as unknown as ReturnType<
    typeof chatApi.useConversations
  >);
});

function mockSendMessage() {
  const sendMessage = vi.fn().mockResolvedValue(undefined);
  mockedChatApi.useSendMessage.mockReturnValue({
    sendMessage,
    cancel: vi.fn(),
    isStreaming: false,
    streamedText: "",
    error: null,
  } as unknown as ReturnType<typeof chatApi.useSendMessage>);
  return sendMessage;
}

describe("ChatPanel: getDiagramContext (ADP-914.8, User Story 1)", () => {
  it("calls sendMessage with the getter's return value as diagramContext", async () => {
    const sendMessage = mockSendMessage();
    const getDiagramContext = vi.fn().mockReturnValue("Diagram title: X\nDiagram type: flowchart");
    const user = userEvent.setup();

    render(<ChatPanel basePath="/api/v1/chat" getDiagramContext={getDiagramContext} />);
    await user.type(screen.getByPlaceholderText("Ask a question…"), "what is this?");
    await user.click(screen.getByText("Send"));

    await waitFor(() => expect(sendMessage).toHaveBeenCalled());
    // Only the first 3 positional args are US1's scope -- the 4th
    // (onComplete) isn't wired until ADP-914.8 User Story 2 (T021).
    expect(sendMessage.mock.calls[0].slice(0, 3)).toEqual([
      "conv-1", "what is this?", "Diagram title: X\nDiagram type: flowchart",
    ]);
  });

  it("calls the getter fresh at send time, not a stale captured value", async () => {
    const sendMessage = mockSendMessage();
    let current = "first";
    const getDiagramContext = vi.fn(() => current);
    const user = userEvent.setup();

    render(<ChatPanel basePath="/api/v1/chat" getDiagramContext={getDiagramContext} />);
    await user.type(screen.getByPlaceholderText("Ask a question…"), "one");
    await user.click(screen.getByText("Send"));
    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(1));

    current = "second";
    await user.type(screen.getByPlaceholderText("Ask a question…"), "two");
    await user.click(screen.getByText("Send"));
    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(2));

    expect(sendMessage.mock.calls[0][2]).toBe("first");
    expect(sendMessage.mock.calls[1][2]).toBe("second");
  });

  it("calls sendMessage with undefined diagramContext when no getter is given", async () => {
    const sendMessage = mockSendMessage();
    const user = userEvent.setup();

    render(<ChatPanel basePath="/api/v1/chat" />);
    await user.type(screen.getByPlaceholderText("Ask a question…"), "hi");
    await user.click(screen.getByText("Send"));

    await waitFor(() => expect(sendMessage).toHaveBeenCalled());
    expect(sendMessage.mock.calls[0][2]).toBeUndefined();
  });
});

describe("ChatPanel: onAssistantReply / onStreamingChange (ADP-914.8, User Story 2)", () => {
  it("wires onAssistantReply through to sendMessage's onComplete argument", async () => {
    const sendMessage = mockSendMessage();
    const onAssistantReply = vi.fn();
    const user = userEvent.setup();

    render(<ChatPanel basePath="/api/v1/chat" onAssistantReply={onAssistantReply} />);
    await user.type(screen.getByPlaceholderText("Ask a question…"), "hi");
    await user.click(screen.getByText("Send"));

    await waitFor(() => expect(sendMessage).toHaveBeenCalled());
    expect(sendMessage.mock.calls[0][3]).toBe(onAssistantReply);
  });

  it("calls onStreamingChange whenever useSendMessage's isStreaming changes", () => {
    const onStreamingChange = vi.fn();
    const sendMessage = vi.fn().mockResolvedValue(undefined);
    const baseReturn = { sendMessage, cancel: vi.fn(), streamedText: "", error: null };

    mockedChatApi.useSendMessage.mockReturnValue({
      ...baseReturn,
      isStreaming: false,
    } as unknown as ReturnType<typeof chatApi.useSendMessage>);
    const { rerender } = render(
      <ChatPanel basePath="/api/v1/chat" onStreamingChange={onStreamingChange} />,
    );

    mockedChatApi.useSendMessage.mockReturnValue({
      ...baseReturn,
      isStreaming: true,
    } as unknown as ReturnType<typeof chatApi.useSendMessage>);
    rerender(<ChatPanel basePath="/api/v1/chat" onStreamingChange={onStreamingChange} />);
    expect(onStreamingChange).toHaveBeenCalledWith(true);

    mockedChatApi.useSendMessage.mockReturnValue({
      ...baseReturn,
      isStreaming: false,
    } as unknown as ReturnType<typeof chatApi.useSendMessage>);
    rerender(<ChatPanel basePath="/api/v1/chat" onStreamingChange={onStreamingChange} />);
    expect(onStreamingChange).toHaveBeenLastCalledWith(false);
  });
});
