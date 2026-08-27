from django.shortcuts import render
from .forms import SimpleCalculatorForm
from .services import calculate_profit


def home(request):
    return render(request, "profit_web/home.html")


def simple_calculator(request):
    form = SimpleCalculatorForm(request.POST or None)
    result = calculate_profit(**form.cleaned_data) if request.method == "POST" and form.is_valid() else None
    return render(request, "profit_web/simple_calculator.html", {"form": form, "result": result})

