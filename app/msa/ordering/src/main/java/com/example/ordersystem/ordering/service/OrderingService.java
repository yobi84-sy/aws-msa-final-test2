package com.example.ordersystem.ordering.service;

import com.example.ordersystem.ordering.domain.Ordering;
import com.example.ordersystem.ordering.dto.OrderCreateDto;
import com.example.ordersystem.ordering.dto.ProductDto;
import com.example.ordersystem.ordering.dto.ProductUpdateStockDto;
import com.example.ordersystem.ordering.repository.OrderingRepository;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;


@Service
@Transactional
public class OrderingService {
    private final OrderingRepository orderingRepository;
    private final RestTemplate restTemplate;
    private final ProductFeign productFeign;
    private final org.springframework.context.ApplicationEventPublisher events;

    public OrderingService(OrderingRepository orderingRepository, RestTemplate restTemplate, ProductFeign productFeign, org.springframework.context.ApplicationEventPublisher events) {
        this.orderingRepository = orderingRepository;
        this.restTemplate = restTemplate;
        this.productFeign = productFeign;
        this.events = events;
    }

    public Ordering orderCreate(OrderCreateDto orderDto, String userId){

//        product get 요청
        String productGetUrl = "http://product-service/product/"+orderDto.getProductId();
        HttpHeaders httpHeaders = new HttpHeaders();
        httpHeaders.set("X-User-Id", userId);
        HttpEntity<String> httpEntity = new HttpEntity<>(httpHeaders);
        ResponseEntity<ProductDto> response =  restTemplate.exchange(productGetUrl, HttpMethod.GET, httpEntity, ProductDto.class);
        ProductDto productDto = response.getBody();
        if (orderDto.getProductCount() == null || orderDto.getProductCount() < 1 || orderDto.getProductCount() > 999) {
            throw new IllegalArgumentException("주문 수량은 1~999개입니다.");
        }
        int quantity = orderDto.getProductCount();
        if(productDto.getStockQuantity() < quantity){
            throw new IllegalArgumentException("재고 부족");
        }else {

//        product put 요청
            String productPutUrl = "http://product-service/product/updatestock";
            httpHeaders.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<ProductUpdateStockDto> updateEntity = new HttpEntity(
                    ProductUpdateStockDto.builder().productId(orderDto.getProductId())
                            .productQuantity(orderDto.getProductCount()).build()
                    , httpHeaders
            );
            restTemplate.exchange(productPutUrl, HttpMethod.PUT, updateEntity, Void.class);
        }
        Ordering ordering = Ordering.builder()
                .memberId(Long.parseLong(userId))
                .productId(orderDto.getProductId())
                .quantity(orderDto.getProductCount())
                .build();
        orderingRepository.save(ordering);
        events.publishEvent(new OrderPlaced(ordering.getId(), productDto.getName(), quantity,
                (long) productDto.getPrice() * quantity, userId));
        return  ordering;
    }


    public Ordering orderFeignCreate(OrderCreateDto orderDto, String userId){

        ProductDto productDto = productFeign.getProductById(orderDto.getProductId(), userId);

        if (orderDto.getProductCount() == null || orderDto.getProductCount() < 1 || orderDto.getProductCount() > 999) {
            throw new IllegalArgumentException("주문 수량은 1~999개입니다.");
        }
        int quantity = orderDto.getProductCount();
        if(productDto.getStockQuantity() < quantity){
            throw new IllegalArgumentException("재고 부족");
        }else {
            ProductUpdateStockDto dto = ProductUpdateStockDto.builder().productId(orderDto.getProductId())
                    .productQuantity(orderDto.getProductCount()).build();
            productFeign.updateProductStock(dto);

        }
        Ordering ordering = Ordering.builder()
                .memberId(Long.parseLong(userId))
                .productId(orderDto.getProductId())
                .quantity(orderDto.getProductCount())
                .build();
        orderingRepository.save(ordering);
        events.publishEvent(new OrderPlaced(ordering.getId(), productDto.getName(), quantity,
                (long) productDto.getPrice() * quantity, userId));
        return  ordering;
    }

}
