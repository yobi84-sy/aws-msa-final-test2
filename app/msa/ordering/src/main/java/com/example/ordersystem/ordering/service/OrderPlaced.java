package com.example.ordersystem.ordering.service;

// DB 커밋 이후 운영자 알림에 사용할 최소 주문 정보
public record OrderPlaced(Long orderId, String productName, int quantity, long total, String memberId) {}

