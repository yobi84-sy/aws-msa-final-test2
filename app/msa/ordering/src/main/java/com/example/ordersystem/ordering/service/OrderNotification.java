package com.example.ordersystem.ordering.service;

import org.slf4j.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.*;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.sns.SnsClient;
import software.amazon.awssdk.services.sns.model.PublishRequest;
import java.time.Duration;

@Component
@ConditionalOnProperty(name = "ORDER_NOTIFICATIONS_ENABLED", havingValue = "true")
public class OrderNotification {
    private static final Logger log = LoggerFactory.getLogger(OrderNotification.class);
    private final SnsClient sns;
    private final String topic;
    public OrderNotification(SnsClient sns, @Value("${ORDER_NOTIFICATION_TOPIC_ARN}") String topic) {
        this.sns = sns; this.topic = topic;
    }

    // 저장이 확정된 뒤 알린다. SNS 오류로 이미 완료된 주문을 실패 처리하지 않는다.
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void send(OrderPlaced order) {
        try {
            sns.publish(PublishRequest.builder().topicArn(topic).subject("[SYONG STORE] 새 주문 알림")
                    .message("주문이 접수되었습니다.\n주문 번호: " + order.orderId()
                            + "\n상품: " + order.productName() + "\n수량: " + order.quantity()
                            + "\n금액: " + order.total() + "원\n회원 번호: " + order.memberId()).build());
        } catch (Exception e) {
            log.error("주문 {} 저장 완료, 운영자 SNS 알림 발행 실패: {}", order.orderId(), e.toString());
        }
    }

    @Configuration
    @ConditionalOnProperty(name = "ORDER_NOTIFICATIONS_ENABLED", havingValue = "true")
    static class SnsConfiguration {
        // IRSA를 사용하고 시간 제한을 설정해 주문 응답 지연을 제한한다.
        @Bean(destroyMethod = "close")
        SnsClient orderSnsClient(@Value("${AWS_REGION:ap-northeast-2}") String region) {
            return SnsClient.builder().region(Region.of(region))
                    .httpClientBuilder(UrlConnectionHttpClient.builder()
                            .connectionTimeout(Duration.ofSeconds(2)).socketTimeout(Duration.ofSeconds(3)))
                    .overrideConfiguration(ClientOverrideConfiguration.builder()
                            .apiCallTimeout(Duration.ofSeconds(5)).build()).build();
        }
    }
}

