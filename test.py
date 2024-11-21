def mokcs():
    print("hello")

    def secondlayer():
        print("olleh")

    def thirdlayer():
        print("dlrow")

    # Вернем только вторую функцию
    return secondlayer

# Получаем функцию secondlayer
func = mokcs()

# Теперь можно вызвать только secondlayer
func()  # Вывод: "olleh"
