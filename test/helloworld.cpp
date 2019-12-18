// サンプルプログラム

#include <stdio.h>

int main(void)
{
	int a = {0};
	int b = atoi("1");
	
	if (strcmp("hello", "world") != 0)
	{
		if (0 < printf("hello, world\n"))
		{
			return 1;
		}
		else if (0 < printf("mollow, world\n"))
		{
			return 2;
		}
		else
		{
			return 3;
		}
	}

	return 0;
}
