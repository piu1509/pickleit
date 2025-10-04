from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from twilio.rest import Client

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

class SendOTPView(APIView):
    """ Sends an OTP via Twilio Verify API """

    def post(self, request):
        phone_number = request.data.get("phone")

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                .verifications.create(to=phone_number, channel="sms")

            return Response({"message": "OTP sent successfully", "verification_sid": verification.sid})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyOTPView(APIView):
    """ Verifies an OTP sent to the user's phone """

    def post(self, request):
        phone_number = request.data.get("phone")
        otp_code = request.data.get("otp")

        if not phone_number or not otp_code:
            return Response({"error": "Phone number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification_check = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                .verification_checks.create(to=phone_number, code=otp_code)

            if verification_check.status == "approved":
                return Response({"message": "OTP verified successfully"})
            else:
                return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
