package com.example.ordersystem.ordering;

import com.example.ordersystem.ordering.dto.*;
import com.example.ordersystem.ordering.domain.Ordering;
import com.example.ordersystem.ordering.repository.OrderingRepository;
import com.example.ordersystem.ordering.service.*;
import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.web.client.RestTemplate;
import software.amazon.awssdk.services.sns.SnsClient;
import software.amazon.awssdk.services.sns.model.PublishRequest;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import org.mockito.ArgumentCaptor;

class OrderFeaturesTest {
    @Test void quantityValidationRejectsZeroNegativeMissingAndExcess() {
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var validator = factory.getValidator();
            for (Integer quantity : new Integer[] {null, 0, -1, 1000}) {
                assertFalse(validator.validate(new OrderCreateDto(1L, quantity)).isEmpty());
            }
            assertTrue(validator.validate(new OrderCreateDto(1L, 3)).isEmpty());
        }
    }

    @Test void successfulOrderPublishesCorrectTotalAndFailureDoesNotPublish() {
        var repository = mock(OrderingRepository.class);
        var product = mock(ProductFeign.class);
        var events = mock(ApplicationEventPublisher.class);
        var service = new OrderingService(repository, new RestTemplate(), product, events);
        when(product.getProductById(2L, "7")).thenReturn(new ProductDto(2L, "test", 1500, 10));
        service.orderFeignCreate(new OrderCreateDto(2L, 3), "7");
        var event = ArgumentCaptor.forClass(OrderPlaced.class);
        verify(events).publishEvent(event.capture());
        assertEquals(4500, event.getValue().total());
        assertEquals(3, event.getValue().quantity());
        reset(events);
        doThrow(new IllegalArgumentException("stock changed")).when(product).updateProductStock(any());
        assertThrows(IllegalArgumentException.class, () -> service.orderFeignCreate(new OrderCreateDto(2L, 3), "7"));
        verifyNoInteractions(events);
    }

    @Test void notificationUsesOperatorTopicAndFailureDoesNotFailCommittedOrder() throws Exception {
        var sns = mock(SnsClient.class);
        var listener = new OrderNotification(sns, "operator-topic");
        listener.send(new OrderPlaced(9L, "test", 2, 3000, "7"));
        var request = ArgumentCaptor.forClass(PublishRequest.class);
        verify(sns).publish(request.capture());
        assertEquals("operator-topic", request.getValue().topicArn());
        assertTrue(request.getValue().message().contains("3000"));
        when(sns.publish(any(PublishRequest.class))).thenThrow(new RuntimeException("SNS unavailable"));
        assertDoesNotThrow(() -> listener.send(new OrderPlaced(10L, "test", 2, 3000, "7")));
        assertEquals(TransactionPhase.AFTER_COMMIT, OrderNotification.class.getMethod("send", OrderPlaced.class)
                .getAnnotation(TransactionalEventListener.class).phase());
    }
}
