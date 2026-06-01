# Clerk 注册未生效排障记录

本文记录一次本地接入 Clerk 后，邮箱注册完成不了、Clerk Dashboard 中看不到新用户、登录也无法进入产品页的问题定位与修复过程。

## 现象

- 前端已配置 `VITE_CLERK_PUBLISHABLE_KEY`。
- 后端已配置 `CLERK_SECRET_KEY`。
- 用户在 `/sign-up` 使用邮箱注册后，Clerk Dashboard 的 Users 中没有出现该邮箱。
- 随后尝试登录也失败，产品页仍显示未认证或被重定向到登录页。

关键判断：如果 Clerk Dashboard 中没有新用户，问题发生在 Clerk 注册流程完成之前，不是后端 `/api/jobs` Bearer 校验阶段。后端认证只影响登录后访问 API，不决定 Clerk 是否创建用户。

## 排查路径

1. 检查前端是否真正挂载 Clerk。

   - `client/src/auth/AuthProvider.tsx` 会在存在 `VITE_CLERK_PUBLISHABLE_KEY` 时包裹 `ClerkProvider`。
   - `client/src/pages/SignUpPage.tsx` 使用 Clerk 的 `<SignUp>`，不是项目自定义的假注册。

2. 检查注册路由是否覆盖 Clerk 的多步骤路径。

   Clerk 邮箱注册通常不是单页一步完成。验证码、继续注册、回调等流程会进入 `/sign-up/...` 子路径。原路由只匹配 `/sign-up`：

   ```tsx
   <Route path="/sign-up" element={<SignUpPage />} />
   ```

   当 Clerk 进入 `/sign-up/...` 时，React Router 会落到通配路由，导致 Clerk 的注册流程中断。流程中断后用户不会真正创建，所以 Dashboard Users 中也查不到该邮箱。

3. 检查诊断组件是否完整。

   项目已有 `ClerkAuthDiagnostics.tsx`，用于显示当前 Clerk 实例与会话状态，但缺少 `client/src/auth/clerkInstance.ts`，导致诊断链路不完整。

4. 检查环境一致性。

   - 前端 `VITE_CLERK_PUBLISHABLE_KEY` 与后端 `CLERK_SECRET_KEY` 必须来自同一个 Clerk instance。
   - Dashboard 要在同一个 instance 的 Development 环境下查 Users。
   - Vite 读取 env 后需要重启 dev server。

## 根因

根因是前端路由没有把 Clerk 的子路径留给 Clerk 组件：

- `/sign-up` 精确匹配不足以承载邮箱验证码等多步骤注册流程。
- `/sign-in` 同理，也应支持 `/sign-in/*`。
- 注册中断发生在 Clerk 用户创建之前，因此 Clerk Dashboard 中不会出现该邮箱。

## 修复

### 1. 放开 Clerk 登录/注册子路径

文件：`client/src/App.tsx`

```tsx
<Route path="/sign-in/*" element={<SignInPage />} />
<Route path="/sign-up/*" element={<SignUpPage />} />
```

### 2. 使用新版重定向参数

文件：`client/src/pages/SignUpPage.tsx`

```tsx
<SignUp
  routing="path"
  path="/sign-up"
  signInUrl="/sign-in"
  fallbackRedirectUrl="/dashboard"
/>
```

文件：`client/src/pages/SignInPage.tsx`

```tsx
<SignIn
  routing="path"
  path="/sign-in"
  signUpUrl="/sign-up"
  fallbackRedirectUrl="/dashboard"
/>
```

`afterSignInUrl` / `afterSignUpUrl` 在当前 Clerk 类型中已标记为 deprecated，优先使用 `fallbackRedirectUrl` 或 `forceRedirectUrl`。

### 3. 补齐开发诊断

新增文件：`client/src/auth/clerkInstance.ts`

作用：

- 从 publishable key 解码当前 Clerk instance host。
- 配合 `ClerkAuthDiagnostics` 在开发环境显示当前前端连接的 Clerk 实例。
- 方便确认 Dashboard Users 是否查错实例或查错 Development/Production 环境。

### 4. 在登录/注册页显示诊断

文件：

- `client/src/pages/SignInPage.tsx`
- `client/src/pages/SignUpPage.tsx`

开发环境下显示：

- 当前 Clerk instance。
- 当前会话是否已登录。
- 已登录时的 Clerk user id 与邮箱。

## 验证

已执行：

```bash
cd client
npm run build
```

结果：前端构建通过。

手动验证步骤：

1. 轮换并更新本地 `CLERK_SECRET_KEY`，避免泄露风险。
2. 重启后端和 Vite dev server。
3. 打开 `http://localhost:5173/sign-up`。
4. 使用一个未注册邮箱完整走完验证码/邮箱验证流程。
5. 观察页面底部 Clerk 诊断中的 instance host。
6. 在 Clerk Dashboard 的同一个 Development instance 下查看 Users。
7. 注册完成后应跳转 `/dashboard`，侧边栏应显示 Clerk 用户信息。

## 注意事项

- 不要把真实 Clerk key 写入文档、提交记录或 issue。
- 如果日志或终端输出过 `CLERK_SECRET_KEY`，应立即在 Clerk Dashboard 轮换 secret key。
- 如果页面诊断显示已登录且有邮箱，但 Dashboard 搜不到该邮箱，通常是看错 Clerk instance 或看错 Development/Production 环境。
- 如果 Dashboard 已有用户但产品 API 仍返回 401，再进入后端 Bearer 校验排查：查看服务端是否读取到同一 instance 的 `CLERK_SECRET_KEY`，以及是否有 `[clerk] verifyToken failed` 日志。
