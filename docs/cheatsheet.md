# Laravel Cheat Sheet

| Laravel (PHP) | PyLara (Python) |
|---|---|
| `composer create-project laravel/laravel blog` | `pylara new blog` |
| `php artisan serve` | `python -m manage serve` |
| `php artisan route:list` | `python -m manage route:list` |
| `php artisan make:controller PostController --resource` | `python -m manage make:controller PostController --resource` |
| `php artisan make:model Post -m` | `python -m manage make:model Post -m` |
| `php artisan make:middleware X` | `python -m manage make:middleware X` |
| `php artisan migrate` / `migrate:rollback` / `migrate:status` | `python -m manage migrate` / `migrate:rollback` / `migrate:status` |
| `Route::get('/u/{id}', [C::class, 'show'])` | `app.get("/u/{id}", [C, "show"])` |
| `Route::resource('posts', PostController::class)` | `app.resource("posts", PostController)` |
| `Route::get(...)->name('x')` | `app.get(...).named("x")` |
| `Route::get(...)->middleware(M::class)` | `app.get(...).with_middleware(M)` |
| `Route::prefix('api')->group(fn)` | `app.group({"prefix": "/api"}, fn)` |
| `route('x', ['id' => 1])` | `route("x", id=1)` |
| `$request->input('a')`, `$request->all()` | `request.input("a")`, `request.all()` |
| `$request->only(['a','b'])` | `request.only("a", "b")` |
| `$request->validate(['a' => 'required\|email'])` | `request.validate({"a": "required\|email"})` |
| `return response()->json($x, 201)` | `return JsonResponse(x, 201)` or `self.json(x, 201)` |
| `return redirect('/home')` | `return RedirectResponse("/home")` or `self.redirect("/home")` |
| `abort(404)` | `abort(404)` |
| `view('welcome', ['a' => 1])` | `view("welcome", a=1)` |
| Blade `{{ $x }}`, `{!! $x !!}` | `{{ x }}`, `{!! x !!}` |
| Blade `@if`, `@foreach`, `@extends`, `@section`, `@include` | `{% if %}`, `{% for %}`, `{% extends %}`, `{% block %}`, `{% include %}` |
| `config('app.name')` | `config("app.name")` |
| `env('APP_DEBUG', false)` | `env("APP_DEBUG", False)` |
| `User::find(1)`, `User::findOrFail(1)` | `User.find(1)`, `User.find_or_fail(1)` |
| `User::where('a', 1)->first()` | `User.where("a", 1).first()` |
| `User::create([...])` | `User.create(**data)` |
| `$user->save()`, `$user->delete()` | `user.save()`, `user.delete()` |
| `$fillable`, `$hidden`, `$casts`, `SoftDeletes` | `fillable`, `hidden`, `casts`, `soft_deletes = True` |
| `$this->hasMany(Post::class)` | `self.has_many(Post)` |
| `$this->belongsTo(User::class)` | `self.belongs_to(User)` |
| `User::paginate(15)` | `User.query().paginate(per_page=15, page=1)` |
| `Schema::create('t', fn (Blueprint $t) => ...)` | `Schema.create("t", lambda t: [...])` |
| `$table->string('name')->nullable()` | `t.string("name").nullable()` |
| `$table->foreignId('user_id')->constrained()` | `t.integer("user_id")` + `t.foreign("user_id").references("id").on("users")` |
| `Hash::make($p)` / `Hash::check($p, $h)` | `Hash.make(p)` / `Hash.check(p, h)` |
| `collect($items)->pluck('a')` | `collect(items).pluck("a")` |
| `session('cart')`, `session(['cart' => 1])` | `request.session.get("cart")`, `request.session.put("cart", 1)` |
| `redirect()->with('status', 'Saved')` | `request.session.flash("status", "Saved")` |
| `@csrf` | `{!! csrf_field !!}` |
| `VerifyCsrfToken` / `$except` | `VerifyCsrfToken` / `except_paths = [...]` |
| `auth` middleware | `RequireLogin` |
| `php artisan key:generate` | `python -m manage key:generate` |
| `$request->file('a')->store('dir')` | `request.file("a").save("dir")` |
| `'photo' => 'required\|image\|max:2048'` | `"photo": "required\|file\|mimes:png,jpg\|max_kb:2048"` |
| `View::share('k', $v)` | `app.share("k", v)` |
| `$this->get('/')->assertStatus(200)` | `client.get("/").status_code == 200` |
| `app()->bind(...)`, `app()->singleton(...)`, `app()->make(...)` | `app.bind(...)`, `app.singleton(...)`, `app.make(...)` |
| Service providers `register()` / `boot()` | `ServiceProvider.register()` / `boot()` |
| `App\Http\Middleware\X` `handle($request, Closure $next)` | `class X(Middleware): def handle(self, request, next)` |

## Concepts that differ

- **Parameters are named after your function arguments**, and arrive as strings.
- **No facades**: you import functions and classes directly.
- **`fillable` is required** for mass assignment (closed by default).
- **`except` is `except_`** because `except` is a Python keyword.
- **No Eloquent magic properties for relations**: call the relationship method, `user.posts()`.
