from rest_framework import serializers
from .models import Appointment
from .models import AppointmentLog
from .models import AppointmentFeedback
from datetime import datetime
from django.utils.timezone import make_aware
from apps.therapists.models import TherapistProfile
from rest_framework import serializers
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from apps.appointments.models import Appointment

class AppointmentSerializer(serializers.ModelSerializer):
    # Input fields (write-only)
    date = serializers.DateField(write_only=True)
    time = serializers.DictField(write_only=True)

    # Output fields (read-only)
    date_output = serializers.SerializerMethodField(read_only=True)
    time_output = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'therapist', 'session_type',
            'status', 'scheduled_at', 'notes',
            'is_recurring', 'recurring_group',
            'date', 'time',  # input
            'date_output', 'time_output',  # output
            'duration_minutes'
        ]
        read_only_fields = ['id', 'patient', 'status', 'notes', 'scheduled_at', 'duration_minutes']

    def get_date_output(self, obj):
        return obj.scheduled_at.date()

    def get_time_output(self, obj):
        start = obj.scheduled_at.time().strftime('%H:%M')
        end_dt = obj.scheduled_at + timedelta(minutes=obj.duration_minutes or 60)
        end = end_dt.time().strftime('%H:%M')
        return {"start": start, "end": end}

    def validate(self, data):
        user = self.context['request'].user
        if user.user_type != 'patient':
            raise serializers.ValidationError("Only patients can book appointments.")

        # Parse time dictionary
        time_dict = data.get('time', {})
        try:
            start_time = datetime.strptime(time_dict['start'], '%H:%M').time()
            end_time = datetime.strptime(time_dict['end'], '%H:%M').time()
        except (KeyError, ValueError):
            raise serializers.ValidationError("Time must include 'start' and 'end' in HH:MM format.")

        if end_time <= start_time:
            raise serializers.ValidationError("End time must be after start time.")

        # Combine to datetime
        scheduled_at = make_aware(datetime.combine(data['date'], start_time))
        duration_minutes = int((datetime.combine(data['date'], end_time) - datetime.combine(data['date'], start_time)).total_seconds() // 60)

        # Double-booking check
        therapist_profile = data.get('therapist')
        if Appointment.objects.filter(therapist=therapist_profile, scheduled_at=scheduled_at).exists():
            raise serializers.ValidationError("This time slot is already booked.")

        # Inject calculated fields
        data['scheduled_at'] = scheduled_at
        data['duration_minutes'] = duration_minutes

        return data

    def create(self, validated_data):
        validated_data['patient'] = self.context['request'].user
        validated_data['status'] = 'pending'
        validated_data.pop('date')
        validated_data.pop('time')
        return super().create(validated_data)

    
class AppointmentLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)

    class Meta:
        model = AppointmentLog
        fields = ['id', 'performed_by_name', 'action', 'notes', 'timestamp']
        



class AppointmentFeedbackSerializer(serializers.ModelSerializer):
    appointment_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = AppointmentFeedback
        fields = '__all__'
        read_only_fields = ('id', 'appointment', 'patient')

    def validate(self, data):
        user = self.context['request'].user
        appointment_id = data['appointment_id']

        # تحقق أن الموعد موجود ويخص المريض وتم
        from .models import Appointment
        try:
            appointment = Appointment.objects.get(id=appointment_id, patient=user, status='completed')
        except Appointment.DoesNotExist:
            raise serializers.ValidationError("You can only rate completed appointments you attended.")

        if hasattr(appointment, 'feedback'):
            raise serializers.ValidationError("Feedback already submitted for this appointment.")

        data['appointment'] = appointment
        return data

    def create(self, validated_data):
        validated_data.pop('appointment_id')
        return super().create(validated_data)
