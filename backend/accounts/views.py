from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # Add user profile info to login response
        data["user"] = UserSerializer(self.user).data
        return data


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens directly upon successful registration
        refresh = RefreshToken.for_user(user)

        # Send Welcome Email to user's registered inbox
        try:
            subject = "Welcome to FinTrack – Account Created Successfully!"
            plain_message = (
                f"Hello {user.first_name or user.username},\n\n"
                f"Welcome to FinTrack! Your smart personal finance management account has been created successfully.\n\n"
                f"Account Overview:\n"
                f"• Username: {user.username}\n"
                f"• Email: {user.email}\n"
                f"• Preferred Currency: {user.preferred_currency}\n\n"
                f"You can now track daily income and expenses, set monthly category budgets, monitor savings goals, and download audited financial statements.\n\n"
                f"Access your financial dashboard: https://financetracker-jgvx.vercel.app/login\n\n"
                f"Best regards,\nThe FinTrack Team"
            )
            html_message = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <div style="background: linear-gradient(135deg, #2563eb, #1d4ed8); padding: 32px 24px; text-align: center; color: white;">
                    <div style="display: inline-block; width: 48px; height: 48px; line-height: 48px; background-color: white; color: #2563eb; font-weight: 800; font-size: 24px; border-radius: 12px; margin-bottom: 12px;">F</div>
                    <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff;">Welcome to FinTrack!</h1>
                    <p style="margin: 8px 0 0; font-size: 14px; opacity: 0.9; color: #dbeafe;">Smart Personal Finance &amp; Expense Management</p>
                </div>
                <div style="padding: 32px 24px; color: #334155;">
                    <p style="font-size: 16px; margin-top: 0;">Hi <strong>{user.first_name or user.username}</strong>,</p>
                    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
                        Your FinTrack account has been successfully created! You are all set to track expenses, manage budgets, hit your savings milestones, and build wealth.
                    </p>
                    
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 24px 0;">
                        <h3 style="margin: 0 0 12px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b;">Account Summary</h3>
                        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                            <tr>
                                <td style="padding: 6px 0; color: #64748b; width: 120px;">Username:</td>
                                <td style="padding: 6px 0; font-weight: 600; color: #0f172a;">{user.username}</td>
                            </tr>
                            <tr>
                                <td style="padding: 6px 0; color: #64748b;">Email:</td>
                                <td style="padding: 6px 0; font-weight: 600; color: #0f172a;">{user.email}</td>
                            </tr>
                            <tr>
                                <td style="padding: 6px 0; color: #64748b;">Currency:</td>
                                <td style="padding: 6px 0; font-weight: 600; color: #0f172a;">{user.preferred_currency}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="text-align: center; margin: 32px 0;">
                        <a href="https://financetracker-jgvx.vercel.app/login" style="background-color: #2563eb; color: #ffffff; padding: 12px 32px; border-radius: 10px; font-weight: 600; text-decoration: none; display: inline-block;">Go to FinTrack Dashboard</a>
                    </div>
                    
                    <p style="font-size: 12px; color: #94a3b8; line-height: 1.5; margin-bottom: 0; border-top: 1px solid #f1f5f9; padding-top: 16px;">
                        If you did not register for this account, please ignore this email.
                    </p>
                </div>
            </div>
            """
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "FinTrack <noreply@fintrack.local>")
            msg = EmailMultiAlternatives(subject, plain_message, from_email, [user.email])
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass

        return Response(
            {
                "message": "User registered successfully.",
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Logged out successfully."},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        try:
            user = User.objects.get(email__iexact=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Send password reset email via console backend or configured SMTP
            reset_url = f"/reset-password?uid={uid}&token={token}"
            send_mail(
                subject="FinTrack Password Reset",
                message=f"Hello {user.username},\n\nUse the link below to reset your password:\n{reset_url}\n\nIf you did not request this, please ignore this email.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fintrack.local"),
                recipient_list=[user.email],
                fail_silently=True,
            )
            # In development/test mode, also return uid & token for easy testing
            return Response(
                {
                    "message": "If an account with this email exists, password reset instructions have been sent.",
                    "dev_reset_data": {"uid": uid, "token": token} if settings.DEBUG else None,
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"message": "If an account with this email exists, password reset instructions have been sent."},
                status=status.HTTP_200_OK,
            )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response(
            {"message": "Password has been reset successfully. You can now log in with your new password."},
            status=status.HTTP_200_OK,
        )
