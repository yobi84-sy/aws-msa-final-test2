package com.example.ordersystem.member.controller;

import com.example.ordersystem.member.service.JwtTokenProvider;
import com.example.ordersystem.member.domain.Member;
import com.example.ordersystem.member.dto.LoginDto;
import com.example.ordersystem.member.dto.MemberRefreshDto;
import com.example.ordersystem.member.dto.MemberSaveReqDto;
import com.example.ordersystem.member.service.MemberService;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/member")
public class MemberController {
    private final MemberService memberService;
    private final JwtTokenProvider jwtTokenProvider;

    @Value("${jwt.secretKeyRt}")
    private String secretKeyRt;

    public MemberController(MemberService memberService, JwtTokenProvider jwtTokenProvider) {
        this.memberService = memberService;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @PostMapping("/create")
    public ResponseEntity<?> memberCreate(@RequestBody MemberSaveReqDto memberSaveReqDto){
        Long memberId = memberService.save(memberSaveReqDto);

        Map<String, Object> response = new HashMap<>();
        response.put("id", memberId);
        response.put("message", "회원가입이 완료되었습니다.");
        return new ResponseEntity<>(response, HttpStatus.CREATED);
    }

    @PostMapping("/doLogin")
    public ResponseEntity<?> doLogin(@RequestBody LoginDto dto){
        Member member = memberService.login(dto);
        String token = jwtTokenProvider.createToken(member.getId().toString(), member.getRole().toString());
        String refreshToken = jwtTokenProvider.createRefreshToken(member.getLoginId(), member.getRole().toString());

        Map<String, Object> loginInfo = new HashMap<>();
        loginInfo.put("id", member.getId());
        loginInfo.put("name", member.getName());
        loginInfo.put("nickname", member.getNickname());
        loginInfo.put("loginId", member.getLoginId());
        loginInfo.put("email", member.getEmail());
        loginInfo.put("role", member.getRole());
        loginInfo.put("token", token);
        loginInfo.put("refreshToken", refreshToken);
        loginInfo.put("message", "로그인에 성공했습니다.");
        return new ResponseEntity<>(loginInfo, HttpStatus.OK);
    }

    @PostMapping("/refresh-token")
    public ResponseEntity<?> generateNewAt(@RequestBody MemberRefreshDto dto){
        try {
            Claims claims = Jwts.parserBuilder()
                    .setSigningKey(secretKeyRt)
                    .build()
                    .parseClaimsJws(dto.getRefreshToken())
                    .getBody();

            String loginId = claims.getSubject();
            Member member = memberService.findByLoginId(loginId);
            String role = claims.get("role", String.class);
            String newAccessToken = jwtTokenProvider.createToken(member.getId().toString(), role);

            Map<String, Object> tokenMap = new HashMap<>();
            tokenMap.put("token", newAccessToken);
            return new ResponseEntity<>(tokenMap, HttpStatus.OK);
        } catch (Exception e) {
            return new ResponseEntity<>("refresh token 검증 실패", HttpStatus.BAD_REQUEST);
        }
    }
}
