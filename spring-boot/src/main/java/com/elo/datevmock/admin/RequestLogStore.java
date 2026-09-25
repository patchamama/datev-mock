package com.elo.datevmock.admin;

import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Set;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Ports {@code app/request_log.py}'s ring buffer + pub-sub: a bounded
 * history of the last 1000 request/response log entries plus live
 * broadcast to any connected SSE subscriber.
 */
@Component
public class RequestLogStore {

    private static final int BUFFER_SIZE = 1000;
    private static final int SUBSCRIBER_QUEUE_SIZE = 200;

    private final Deque<RequestLogEntry> buffer = new ArrayDeque<>(BUFFER_SIZE);
    private final Set<BlockingQueue<RequestLogEntry>> subscribers = ConcurrentHashMap.newKeySet();
    private final AtomicLong seqCounter = new AtomicLong(0);

    public long nextSeq() {
        return seqCounter.incrementAndGet();
    }

    public synchronized void addEntry(RequestLogEntry entry) {
        if (buffer.size() >= BUFFER_SIZE) {
            buffer.removeFirst();
        }
        buffer.addLast(entry);
        for (BlockingQueue<RequestLogEntry> queue : subscribers) {
            // Slow/disconnected client: drop this entry for it rather than
            // blocking every request in the app on one stuck consumer.
            queue.offer(entry);
        }
    }

    public synchronized List<RequestLogEntry> getBacklog() {
        return new ArrayList<>(buffer);
    }

    public BlockingQueue<RequestLogEntry> registerSubscriber() {
        BlockingQueue<RequestLogEntry> queue = new LinkedBlockingQueue<>(SUBSCRIBER_QUEUE_SIZE);
        subscribers.add(queue);
        return queue;
    }

    public void unregisterSubscriber(BlockingQueue<RequestLogEntry> queue) {
        subscribers.remove(queue);
    }
}
