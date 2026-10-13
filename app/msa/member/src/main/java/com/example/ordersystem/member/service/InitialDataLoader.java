package com.example.ordersystem.member.service;

import com.example.ordersystem.member.domain.Member;
import com.example.ordersystem.member.domain.Role;
import com.example.ordersystem.member.repository.MemberRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

@Component
public class InitialDataLoader implements CommandLineRunner {
    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    public InitialDataLoader(MemberRepository memberRepository, PasswordEncoder passwordEncoder) {
        this.memberRepository = memberRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        if(memberRepository.findByLoginId("admin").isPresent() || memberRepository.findByEmail("admin@naver.com").isPresent()) {
            return;
        }

        Member member = Member.builder()
                .name("관리자")
                .loginId("admin")
                .nickname("관리자")
                .email("admin@naver.com")
                .password(passwordEncoder.encode("12341234"))
                .role(Role.ADMIN)
                .build();
        memberRepository.save(member);
    }
}
